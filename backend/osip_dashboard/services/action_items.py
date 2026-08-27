"""Operational action items - risk breach exceptions, accounting close
steps, and future domain to-dos. See ActionItem's docstring in
persistence/models.py for why this is deliberately not a DQ issue model.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from osip_dashboard.persistence.models import ActionItem, utcnow


def create_action_item(
    session: Session,
    *,
    domain: str,
    kind: str,
    title: str,
    created_by: str,
    dataset_type: str | None = None,
    scope_code: str | None = None,
    reference_key: str | None = None,
) -> ActionItem:
    item = ActionItem(
        domain=domain,
        kind=kind,
        title=title,
        dataset_type=dataset_type,
        scope_code=scope_code,
        reference_key=reference_key,
        status="open",
        created_by=created_by,
        created_at=utcnow(),
    )
    session.add(item)
    session.flush()
    return item


def get_action_item(session: Session, item_id: UUID) -> ActionItem | None:
    return session.get(ActionItem, item_id)


def list_action_items(
    session: Session,
    *,
    domain: str | None = None,
    status: str | None = None,
    kind: str | None = None,
) -> list[ActionItem]:
    statement = select(ActionItem).order_by(ActionItem.created_at.desc())
    if domain is not None:
        statement = statement.where(ActionItem.domain == domain)
    if status is not None:
        statement = statement.where(ActionItem.status == status)
    if kind is not None:
        statement = statement.where(ActionItem.kind == kind)
    return list(session.scalars(statement))


def assign_action_item(
    session: Session,
    item: ActionItem,
    *,
    owner_id: str | None,
    due_date: date | None,
    reason: str,
    actor_id: str,
) -> None:
    if item.status == "resolved":
        raise ValueError("Нельзя назначить ответственного для закрытого пункта")
    if not reason.strip():
        raise ValueError("Требуется обоснование назначения")
    item.owner_id = owner_id
    item.due_date = due_date if owner_id else None
    item.assigned_by = actor_id
    item.assigned_at = utcnow()
    item.assignment_reason = reason.strip()


def resolve_action_item(session: Session, item: ActionItem, *, comment: str, actor_id: str) -> None:
    if item.status == "resolved":
        raise ValueError("Пункт уже закрыт")
    if not comment.strip():
        raise ValueError("Требуется комментарий закрытия")
    item.status = "resolved"
    item.resolved_by = actor_id
    item.resolved_at = utcnow()
    item.resolution_comment = comment.strip()


def reopen_action_item(session: Session, item: ActionItem, *, reason: str, actor_id: str) -> None:
    if item.status != "resolved":
        raise ValueError("Можно переоткрыть только закрытый пункт")
    if not reason.strip():
        raise ValueError("Требуется причина повторного открытия")
    item.status = "open"
    item.resolved_by = None
    item.resolved_at = None
    item.resolution_comment = None
    item.assignment_reason = reason.strip()
    item.assigned_by = actor_id
    item.assigned_at = utcnow()


def is_overdue(item: ActionItem) -> bool:
    # date.today(), not utcnow().date() - see services/multi_source.py's
    # _readiness_status for why (this app runs on a machine configured for
    # the business's own timezone, confirmed UTC+5).
    return bool(item.status == "open" and item.owner_id and item.due_date and item.due_date < date.today())


def action_item_payload(item: ActionItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "domain": item.domain,
        "kind": item.kind,
        "title": item.title,
        "dataset_type": item.dataset_type,
        "scope_code": item.scope_code,
        "reference_key": item.reference_key,
        "status": item.status,
        "owner_id": item.owner_id,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "created_by": item.created_by,
        "created_at": item.created_at.isoformat(),
        "assigned_by": item.assigned_by,
        "assigned_at": item.assigned_at.isoformat() if item.assigned_at else None,
        "assignment_reason": item.assignment_reason,
        "resolved_by": item.resolved_by,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        "resolution_comment": item.resolution_comment,
        "is_overdue": is_overdue(item),
    }
