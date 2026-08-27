"""Manual review and publication workflow for immutable imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from osip_dashboard.persistence.models import (
    AuditEvent,
    DataQualityAcknowledgement,
    DataQualityIssueRecord,
    ImportBatch,
    ImportStatus,
    Portfolio,
    utcnow,
)


class WorkflowError(ValueError):
    """A requested state transition violates the import workflow."""


@dataclass(frozen=True)
class Actor:
    actor_id: str
    roles: frozenset[str]
    portfolios: frozenset[str] = frozenset({"*"})
    # Domain scopes are intentionally separate from portfolio scopes. A user
    # may be allowed to work with brokerage data while having no access to
    # corporate-finance or accounting datasets.
    domains: frozenset[str] = frozenset({"*"})


def get_import_or_error(
    session: Session, import_id: UUID, *, for_update: bool = False
) -> ImportBatch:
    statement = select(ImportBatch).where(ImportBatch.id == import_id)
    if for_update:
        statement = statement.with_for_update()
    batch = session.scalar(statement)
    if batch is None:
        raise LookupError("Загрузка не найдена")
    return batch


def approve_import(
    session: Session,
    import_id: UUID,
    *,
    actor: Actor,
    comment: str,
    acknowledged_codes: Iterable[str],
) -> ImportBatch:
    batch = get_import_or_error(session, import_id, for_update=True)
    if batch.status != ImportStatus.VALIDATED:
        raise WorkflowError("Утвердить можно только проверенную загрузку")
    if batch.uploader_id == actor.actor_id:
        raise WorkflowError("Контроль четырёх глаз запрещает утверждать собственную загрузку")
    justification = comment.strip()
    if not justification:
        raise WorkflowError("Для утверждения требуется обоснование проверяющего")

    issues = list(batch.snapshot.issues if batch.snapshot else [])
    required_issues = [
        issue for issue in issues if issue.severity in {"blocker", "high"}
    ]
    supplied = {code.strip() for code in acknowledged_codes if code.strip()}
    required_codes = {issue.code for issue in required_issues}
    missing = sorted(required_codes - supplied)
    if missing:
        raise WorkflowError(
            "При утверждении необходимо подтвердить каждый блокирующий/высокий код DQ: "
            + ", ".join(missing)
        )

    for issue in required_issues:
        if issue.acknowledgement is None:
            issue.acknowledgement = DataQualityAcknowledgement(
                actor_id=actor.actor_id,
                comment=justification,
            )
    batch.status = ImportStatus.APPROVED
    batch.reviewer_id = actor.actor_id
    batch.review_comment = justification
    batch.approved_at = utcnow()
    _audit(
        session,
        batch,
        actor.actor_id,
        "import.approved",
        {"acknowledged_codes": sorted(supplied), "comment": justification},
    )
    session.flush()
    return batch


def reject_import(
    session: Session,
    import_id: UUID,
    *,
    actor: Actor,
    reason: str,
) -> ImportBatch:
    batch = get_import_or_error(session, import_id, for_update=True)
    if batch.status not in {ImportStatus.VALIDATED, ImportStatus.APPROVED}:
        raise WorkflowError("Отклонить можно только проверенную или утверждённую загрузку")
    rejection_reason = reason.strip()
    if not rejection_reason:
        raise WorkflowError("Для отклонения требуется причина")
    batch.status = ImportStatus.REJECTED
    batch.rejection_reason = rejection_reason
    _audit(
        session,
        batch,
        actor.actor_id,
        "import.rejected",
        {"reason": rejection_reason},
    )
    session.flush()
    return batch


def withdraw_import(
    session: Session,
    import_id: UUID,
    *,
    actor: Actor,
    reason: str,
) -> ImportBatch:
    """Remove a published version from operational reads without deleting evidence."""
    batch = get_import_or_error(session, import_id, for_update=True)
    if batch.status != ImportStatus.PUBLISHED:
        raise WorkflowError("Снять с публикации можно только опубликованную версию")
    withdrawal_reason = reason.strip()
    if not withdrawal_reason:
        raise WorkflowError("Для снятия с публикации требуется причина")
    batch.status = ImportStatus.WITHDRAWN
    # The existing reason field retains a human-readable explanation in the
    # immutable import record; the audit event records the distinct action.
    batch.rejection_reason = withdrawal_reason
    _audit(
        session,
        batch,
        actor.actor_id,
        "import.withdrawn",
        {"reason": withdrawal_reason},
    )
    session.flush()
    return batch


def get_dq_issue_or_error(session: Session, issue_id: UUID) -> DataQualityIssueRecord:
    issue = session.get(DataQualityIssueRecord, issue_id)
    if issue is None:
        raise LookupError("Замечание по качеству данных не найдено")
    return issue


def assign_dq_issue(
    session: Session,
    issue_id: UUID,
    *,
    actor: Actor,
    owner_id: str | None,
    due_date: date | None,
    reason: str,
) -> DataQualityIssueRecord:
    """Set or clear the owner and due date tracked against a DQ finding.

    This is independent of acknowledgement: acknowledging a finding records
    that a reviewer accepted it during approval, while assignment tracks who
    is responsible for remediating it and by when.
    """
    issue = get_dq_issue_or_error(session, issue_id)
    justification = reason.strip()
    if not justification:
        raise WorkflowError("Для назначения ответственного требуется обоснование")
    normalized_owner = (owner_id or "").strip() or None
    if normalized_owner is None and due_date is not None:
        raise WorkflowError("Срок устранения нельзя задать без ответственного")
    issue.owner_id = normalized_owner
    issue.due_date = due_date
    session.add(
        AuditEvent(
            import_id=issue.snapshot.import_id,
            actor_id=actor.actor_id,
            action="dq_issue.assigned" if normalized_owner else "dq_issue.unassigned",
            detail={
                "issue_id": str(issue.id),
                "code": issue.code,
                "owner_id": normalized_owner,
                "due_date": due_date.isoformat() if due_date else None,
                "reason": justification,
            },
        )
    )
    session.flush()
    return issue


def publish_import(
    session: Session,
    import_id: UUID,
    *,
    actor: Actor,
) -> ImportBatch:
    batch = get_import_or_error(session, import_id, for_update=True)
    if batch.status != ImportStatus.APPROVED:
        raise WorkflowError("Опубликовать можно только утверждённую загрузку")
    session.execute(
        select(Portfolio)
        .where(Portfolio.code == batch.portfolio_code)
        .with_for_update()
    ).scalar_one()
    previous = session.scalar(
        select(ImportBatch).where(
            ImportBatch.portfolio_code == batch.portfolio_code,
            ImportBatch.report_date == batch.report_date,
            ImportBatch.status == ImportStatus.PUBLISHED,
            ImportBatch.id != batch.id,
        )
    )
    if previous is not None:
        previous.status = ImportStatus.SUPERSEDED
        _audit(
            session,
            previous,
            actor.actor_id,
            "import.superseded",
            {"superseded_by": str(batch.id)},
        )
        session.flush()

    batch.status = ImportStatus.PUBLISHED
    batch.publisher_id = actor.actor_id
    batch.published_at = utcnow()
    _audit(
        session,
        batch,
        actor.actor_id,
        "import.published",
        {"superseded_import_id": str(previous.id) if previous else None},
    )
    session.flush()
    return batch


def publish_import_source_first(
    session: Session,
    import_id: UUID,
    *,
    actor_id: str = "source-system",
) -> ImportBatch:
    """Publish a parsed OSIP source in the local trusted-source mode.

    Hosted/controlled deployments retain the four-eyes and DQ acknowledgement
    gates. A local domain owner is only asking the dashboard to present the
    workbook they supplied, so semantic DQ findings stay attached as warnings
    without preventing the source-backed view from appearing.
    """
    batch = get_import_or_error(session, import_id, for_update=True)
    if batch.status not in {ImportStatus.VALIDATED, ImportStatus.APPROVED}:
        raise WorkflowError("Источник можно опубликовать только после успешного разбора")
    previous = session.scalar(
        select(ImportBatch).where(
            ImportBatch.portfolio_code == batch.portfolio_code,
            ImportBatch.report_date == batch.report_date,
            ImportBatch.status == ImportStatus.PUBLISHED,
            ImportBatch.id != batch.id,
        )
    )
    if previous is not None:
        previous.status = ImportStatus.SUPERSEDED
        _audit(
            session,
            previous,
            actor_id,
            "import.superseded",
            {"superseded_by": str(batch.id), "publication_basis": "trusted_source_local"},
        )
    batch.status = ImportStatus.PUBLISHED
    batch.publisher_id = actor_id
    batch.published_at = utcnow()
    _audit(
        session,
        batch,
        actor_id,
        "import.source_first_published",
        {
            "publication_basis": "trusted_source_local",
            "dq_policy": "informational",
            "superseded_import_id": str(previous.id) if previous else None,
        },
    )
    session.flush()
    return batch


def _audit(
    session: Session,
    batch: ImportBatch,
    actor_id: str,
    action: str,
    detail: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            import_batch=batch,
            actor_id=actor_id,
            action=action,
            detail=detail or {},
        )
    )
