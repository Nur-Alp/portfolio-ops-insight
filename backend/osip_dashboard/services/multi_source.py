"""Controlled multi-source upload, child-dataset workflow, and read models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import hashlib
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from osip_dashboard.ingestion.multi_source import (
    PARSER_VERSION,
    ParsedDataset,
    SourceDetectionError,
    detect_source,
    parse_detected_dataset,
    validate_source_filename,
)
from osip_dashboard.i18n import localize_text
from osip_dashboard.services.date_provenance import filename_date_mismatch
from osip_dashboard.services.fx_rates import resolve_export_fx_rate
from osip_dashboard.persistence.models import (
    DatasetAuditEvent,
    ClientIdentityResolution,
    DatasetIssue,
    DatasetRecord,
    DatasetVersion,
    ImportBatch,
    ImportStatus,
    PortfolioSnapshotRecord,
    ReconciliationResult,
    SourceUpload,
    utcnow,
)
from osip_dashboard.storage import BlobStore


INACTIVE = {ImportStatus.WITHDRAWN, ImportStatus.REJECTED, ImportStatus.FAILED}


def create_source_upload(
    session: Session,
    blob_store: BlobStore,
    *,
    filename: str,
    content: bytes,
    uploader_id: str,
    max_upload_bytes: int,
) -> tuple[SourceUpload, bool]:
    safe_filename, file_format = validate_source_filename(filename, content, max_upload_bytes)
    source_sha256 = hashlib.sha256(content).hexdigest()
    # Identical bytes are deduplicated within one operator's ownership scope.
    # A different operator may intentionally re-upload the same workbook so
    # it becomes visible in that operator's private domain workspace; the
    # content-addressed blob remains shared and immutable.
    existing = session.scalar(select(SourceUpload).where(
        SourceUpload.source_sha256 == source_sha256,
        SourceUpload.uploader_id == uploader_id,
    ))
    if existing is not None:
        return existing, True
    storage_key = blob_store.put(source_sha256, content, suffix=f".{file_format}")
    detection = detect_source(blob_store.path_for(storage_key), file_format)
    upload = SourceUpload(
        source_sha256=source_sha256,
        original_filename=safe_filename,
        storage_key=storage_key,
        file_format=file_format,
        detected_source_type=detection["source_type"],
        detection=detection,
        uploader_id=uploader_id,
    )
    session.add(upload)
    try:
        session.flush()
    except IntegrityError:
        # Lost a race against another request for the same (sha256,
        # uploader_id) - uq_source_upload_hash_uploader is the actual
        # guarantee here, the "existing" check above only sees already-
        # committed state. Same pattern as the OSIP upload path's identical
        # race (services/imports.py's import_workbook).
        session.rollback()
        existing = session.scalar(select(SourceUpload).where(
            SourceUpload.source_sha256 == source_sha256,
            SourceUpload.uploader_id == uploader_id,
        ))
        assert existing is not None, "unique violation implies a concurrent winner exists"
        return existing, True
    return upload, False


def _add_with_version_retry(session: Session, next_version, build_row, *, max_attempts: int = 5):
    """Insert a versioned row, retrying its version number on a collision.

    ``next_version`` computes the version to try (max existing + 1) and
    ``build_row`` builds the ORM object for a given version. Both a
    materialize double-click and a genuine concurrent request from another
    tab can race this exact "read max, add one" check the same way the
    upload-dedup and publish races above do - the DB-level unique index
    (uq_dataset_scope_date_version) is the actual guarantee, not the read.
    Unlike those two, the fix here is a bounded retry (not "return the
    existing row") because the loser's own row is still meant to exist,
    just under a version number one higher than it guessed.
    """
    for attempt in range(max_attempts):
        version = next_version()
        row = build_row(version)
        session.add(row)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            if attempt == max_attempts - 1:
                raise
            continue
        return row
    raise AssertionError("unreachable")


def materialize_datasets(
    session: Session,
    blob_store: BlobStore,
    upload: SourceUpload,
    *,
    assignments: list[dict[str, str | None]],
    uploader_id: str,
) -> list[DatasetVersion]:
    if upload.detected_source_type == "osip_portfolio":
        raise SourceDetectionError("Для OSIP используйте совместимый импорт с назначением портфеля")
    available = {item["key"]: item for item in upload.detection.get("datasets", [])}
    requested_keys = [str(item.get("detected_key") or "") for item in assignments]
    if not requested_keys or len(set(requested_keys)) != len(requested_keys):
        raise SourceDetectionError("Выберите хотя бы один уникальный раздел рабочей книги")
    results: list[DatasetVersion] = []
    for assignment in assignments:
        key = str(assignment.get("detected_key") or "")
        proposal = available.get(key)
        if proposal is None:
            raise SourceDetectionError(f"Раздел «{key}» не найден в результате определения")
        scope = str(assignment.get("scope_code") or proposal.get("scope_code") or "").strip().upper()
        active = session.scalar(
            select(DatasetVersion).where(
                DatasetVersion.source_upload_id == upload.id,
                DatasetVersion.dataset_type == proposal["dataset_type"],
                DatasetVersion.detected_key == key,
                DatasetVersion.scope_code == scope,
                DatasetVersion.status.not_in(INACTIVE),
            )
        )
        if active is not None:
            results.append(active)
            continue
        try:
            parsed = parse_detected_dataset(blob_store.path_for(upload.storage_key), upload.detection, key, scope)
        except Exception:
            def next_failed_version() -> int:
                return (
                    session.scalar(select(func.max(DatasetVersion.version)).where(
                        DatasetVersion.dataset_type == proposal["dataset_type"],
                        DatasetVersion.scope_code == scope,
                        DatasetVersion.business_date.is_(None),
                    )) or 0
                ) + 1

            def build_failed(version: int) -> DatasetVersion:
                return DatasetVersion(
                    source_upload=upload, dataset_type=proposal["dataset_type"], detected_key=key,
                    scope_type=proposal.get("scope_type") or "global", scope_code=scope,
                    parser_version=PARSER_VERSION, version=version, status=ImportStatus.FAILED,
                    summary={}, uploader_id=uploader_id,
                    error_message="Не удалось разобрать выбранный раздел рабочей книги; исходный файл сохранён для проверки.",
                )

            failed = _add_with_version_retry(session, next_failed_version, build_failed)
            _audit(session, failed, uploader_id, "dataset.failed", {"parser_version": PARSER_VERSION})
            results.append(failed)
            continue

        def next_version() -> int:
            return (
                session.scalar(
                    select(func.max(DatasetVersion.version)).where(
                        DatasetVersion.dataset_type == parsed.dataset_type,
                        DatasetVersion.scope_code == parsed.scope_code,
                        or_(
                            DatasetVersion.business_date == parsed.business_date,
                            DatasetVersion.source_report_date == parsed.source_report_date,
                        ),
                    )
                ) or 0
            ) + 1
        summary = parsed.summary
        if parsed.dataset_type == "accounting_portfolio_detail":
            # The accounting portfolio workbook doesn't declare which OSIP
            # portfolio it represents - the uploader must say so explicitly
            # (same discipline as OSIP's own import, which never infers a
            # portfolio code from a filename). Reconciliation only runs when
            # this is provided; it is not guessed from the sheet name.
            reconciliation_portfolio_code = str(assignment.get("reconciliation_portfolio_code") or "").strip().upper() or None
            summary = {**summary, "reconciliation_portfolio_code": reconciliation_portfolio_code}
        def build_dataset(version: int) -> DatasetVersion:
            return DatasetVersion(
                source_upload=upload,
                dataset_type=parsed.dataset_type,
                detected_key=parsed.detected_key,
                scope_type=parsed.scope_type,
                scope_code=parsed.scope_code,
                source_report_date=parsed.source_report_date,
                business_date=parsed.business_date,
                generated_at=upload.created_at,
                parser_version=PARSER_VERSION,
                version=version,
                status=ImportStatus.VALIDATED,
                summary=summary,
                uploader_id=uploader_id,
                validated_at=utcnow(),
            )

        dataset = _add_with_version_retry(session, next_version, build_dataset)
        _persist_parsed(session, dataset, parsed)
        _audit(session, dataset, uploader_id, "dataset.validated", {"record_count": len(parsed.records)})
        results.append(dataset)
    session.flush()
    return results


def approve_dataset(
    session: Session,
    dataset: DatasetVersion,
    actor_id: str,
    comment: str,
    codes: list[str],
    *,
    mapping_confirmed: bool = False,
) -> None:
    if dataset.status != ImportStatus.VALIDATED:
        raise ValueError("Утверждать можно только проверенный набор данных")
    # Not blocked for the uploader: per docs/domain-upload-instructions.md,
    # the normal model is one responsible operator per domain who uploads
    # and then uses the dashboard themselves, not a separate four-eyes
    # reviewer. Since visibility is also uploader-scoped (_has_uploader_access
    # in routes/multi_source.py), a genuinely separate reviewer wouldn't be
    # able to see this dataset to approve it anyway.
    if not comment.strip():
        raise ValueError("Требуется обоснование утверждения")
    if dataset.dataset_type != "portfolio_snapshot":
        mapping = dataset.summary.get("mapping", {}) if isinstance(dataset.summary, dict) else {}
        if mapping.get("missing_fields") and not mapping.get("mapping_confirmed") and not mapping_confirmed:
            raise ValueError("Необходимо подтвердить неполное сопоставление полей перед утверждением")
    if dataset.dataset_type == "brokerage_trade_ledger":
        mapping = dataset.summary.get("mapping", {}) if isinstance(dataset.summary, dict) else {}
        if mapping.get("confidence") != "high" and not mapping_confirmed:
            raise ValueError("Необходимо явно подтвердить сопоставление столбцов журнала сделок перед утверждением")
        if mapping_confirmed:
            dataset.summary = {**dataset.summary, "mapping": {**mapping, "mapping_confirmed": True}}
    critical = {issue.code for issue in dataset.issues if issue.severity in {"blocker", "high"}}
    missing = critical - set(codes)
    if missing:
        raise ValueError("Не подтверждены обязательные замечания: " + ", ".join(sorted(missing)))
    for issue in dataset.issues:
        if issue.code in critical:
            issue.acknowledged_by = actor_id
            issue.acknowledgement_comment = comment.strip()
    dataset.status = ImportStatus.APPROVED
    dataset.reviewer_id = actor_id
    dataset.review_comment = comment.strip()
    dataset.approved_at = utcnow()
    _audit(session, dataset, actor_id, "dataset.approved", {"acknowledged_codes": sorted(critical)})


def dataset_mapping(dataset: DatasetVersion) -> dict[str, Any]:
    """Return a stable source-to-field preview without rewriting evidence."""
    summary = dataset.summary if isinstance(dataset.summary, dict) else {}
    mapping = summary.get("mapping") if isinstance(summary.get("mapping"), dict) else {}
    fields = mapping.get("fields") if isinstance(mapping.get("fields"), list) else []
    if not fields:
        # Older datasets do not have parser-level column metadata. Expose the
        # normalized fields and their first source location rather than hiding
        # the limitation; a later reparse can add physical column numbers.
        seen: set[str] = set()
        for record in dataset.records:
            source = record.source_ref or {}
            for field, value in record.payload.items():
                if field in seen:
                    continue
                seen.add(field)
                fields.append({
                    "normalized_field": field,
                    "source_header": field,
                    "source_sheet": source.get("sheet_name"),
                    "source_row": source.get("row_number"),
                    "source_column": None,
                    "sample_values": [] if value in (None, "") else [str(value)],
                })
    return {
        "dataset_id": str(dataset.id),
        "dataset_type": dataset.dataset_type,
        "source_filename": dataset.source_upload.original_filename,
        "confidence": str(mapping.get("confidence") or ("high" if fields else "unknown")),
        "mapping_confirmed": bool(mapping.get("mapping_confirmed", False)),
        "confirmed_by": mapping.get("confirmed_by"),
        "confirmation_comment": mapping.get("confirmation_comment"),
        "missing_fields": [str(value) for value in mapping.get("missing_fields", [])],
        "fields": fields,
    }


def confirm_dataset_mapping(session: Session, dataset: DatasetVersion, actor_id: str, comment: str) -> None:
    if dataset.status != ImportStatus.VALIDATED:
        raise ValueError("Сопоставление можно подтвердить только для проверенного набора данных")
    # See approve_dataset: not blocked for the uploader for the same reason.
    justification = comment.strip()
    if not justification:
        raise ValueError("Для подтверждения сопоставления требуется обоснование")
    current = dataset.summary if isinstance(dataset.summary, dict) else {}
    mapping = current.get("mapping") if isinstance(current.get("mapping"), dict) else {}
    dataset.summary = {
        **current,
        "mapping": {
            **mapping,
            "mapping_confirmed": True,
            "confirmed_by": actor_id,
            "confirmation_comment": justification,
        },
    }
    _audit(session, dataset, actor_id, "dataset.mapping_confirmed", {"comment": justification})


def list_client_identity_exceptions(session: Session, status: str = "pending", *, uploader_id: str | None = None) -> list[dict[str, Any]]:
    statement = (
        select(DatasetVersion)
        .options(selectinload(DatasetVersion.source_upload), selectinload(DatasetVersion.records))
        .where(
            DatasetVersion.dataset_type == "client_open_dates",
            DatasetVersion.scope_code == "BROKERAGE",
            DatasetVersion.status.not_in(INACTIVE),
        )
        .order_by(DatasetVersion.created_at.desc())
    )
    if uploader_id is not None:
        statement = statement.where(DatasetVersion.uploader_id == uploader_id)
    datasets = list(session.scalars(statement))
    results: list[dict[str, Any]] = []
    for dataset in datasets:
        candidates = _client_open_date_candidates(session, dataset)
        resolutions = {
            resolution.record_id: resolution
            for resolution in session.scalars(select(ClientIdentityResolution).where(ClientIdentityResolution.dataset_id == dataset.id))
        }
        for record in dataset.records:
            payload = record.payload or {}
            original_status = str(payload.get("match_status") or "unmatched")
            if original_status == "exact":
                continue
            resolution = resolutions.get(record.id)
            current_status = resolution.status if resolution is not None else "pending"
            if status != "all" and current_status != status:
                continue
            normalized = str(payload.get("normalized_name") or "")
            results.append({
                "id": str(resolution.id if resolution else record.id),
                "dataset_id": str(dataset.id),
                "record_id": str(record.id),
                "source_name": str(payload.get("source_name") or ""),
                "normalized_name": normalized,
                "source_ref": record.source_ref,
                "original_match_status": original_status,
                "status": current_status,
                "candidate_accounts": candidates.get(normalized, []),
                "resolved_account": resolution.resolved_account if resolution else None,
                "resolved_by": resolution.resolved_by if resolution else None,
                "resolution_comment": resolution.resolution_comment if resolution else None,
            })
    return results


def resolve_client_identity(
    session: Session,
    record_id: UUID,
    actor_id: str,
    disposition: str,
    account: str | None,
    comment: str,
) -> dict[str, Any]:
    record = session.get(DatasetRecord, record_id)
    if record is None or record.dataset.dataset_type != "client_open_dates":
        raise ValueError("Исключение идентичности клиента не найдено")
    if record.dataset.status in INACTIVE:
        raise ValueError("Нельзя разрешить исключение снятого или отклонённого набора")
    justification = comment.strip()
    if not justification:
        raise ValueError("Для разрешения исключения требуется обоснование")
    normalized_account = (account or "").strip() or None
    if disposition == "confirmed":
        if not normalized_account:
            raise ValueError("Для подтверждённого совпадения требуется лицевой счёт")
        valid_accounts = {
            str(item.payload.get("account"))
            for item in session.scalars(select(DatasetRecord).join(DatasetVersion).where(
                DatasetVersion.dataset_type == "client_account_snapshot",
                DatasetVersion.scope_code == record.dataset.scope_code,
                DatasetVersion.status == ImportStatus.PUBLISHED,
                DatasetRecord.record_type == "client",
            ))
        }
        if normalized_account not in valid_accounts:
            raise ValueError("Выбранный лицевой счёт отсутствует в опубликованном клиентском источнике")
    existing = session.scalar(select(ClientIdentityResolution).where(
        ClientIdentityResolution.dataset_id == record.dataset_id,
        ClientIdentityResolution.record_id == record.id,
    ))
    if existing is None:
        existing = ClientIdentityResolution(dataset_id=record.dataset_id, record_id=record.id, resolved_by=actor_id, resolution_comment=justification)
        session.add(existing)
    existing.status = disposition
    existing.resolved_account = normalized_account if disposition == "confirmed" else None
    existing.resolved_by = actor_id
    existing.resolution_comment = justification
    record_dataset_event(session, record.dataset, actor_id, "client_identity.resolved", {"record_id": str(record.id), "disposition": disposition})
    session.flush()
    return next(item for item in list_client_identity_exceptions(session, "all") if item["record_id"] == str(record.id))


def _client_open_date_candidates(session: Session, dataset: DatasetVersion) -> dict[str, list[str]]:
    latest = latest_published(session, "client_account_snapshot", dataset.scope_code)
    if latest is None:
        return {}
    candidates: dict[str, list[str]] = {}
    for record in latest.records:
        if record.record_type != "client":
            continue
        name = re.sub(r"\s+", " ", str(record.payload.get("client_name") or "").upper()).strip()
        account = str(record.payload.get("account") or "").strip()
        if name and account:
            candidates.setdefault(name, []).append(account)
    return candidates


def compare_datasets(left: DatasetVersion, right: DatasetVersion) -> dict[str, Any]:
    if left.dataset_type != right.dataset_type or left.scope_code != right.scope_code:
        raise ValueError("Сравнивать можно только версии одного набора и области данных")
    left_rows = {record.record_key: record.payload for record in left.records}
    right_rows = {record.record_key: record.payload for record in right.records}
    # `left` is the subject being compared (the route's {dataset_id}); `right`
    # is what it's compared against ({with_id}, the baseline). "Added" means
    # present in the subject but not the baseline - both call sites
    # (RiskVersionComparison, AccountingVersionComparison) pass the newer
    # version as dataset_id and the older one as with_id, so this must read
    # left-relative-to-right, not the other way around.
    added = sorted(set(left_rows) - set(right_rows))
    removed = sorted(set(right_rows) - set(left_rows))
    changed = sorted(key for key in set(left_rows) & set(right_rows) if left_rows[key] != right_rows[key])
    summary_changes: dict[str, dict[str, Any]] = {}
    left_summary = left.summary if isinstance(left.summary, dict) else {}
    right_summary = right.summary if isinstance(right.summary, dict) else {}
    for key in sorted(set(left_summary) | set(right_summary)):
        if left_summary.get(key) != right_summary.get(key):
            summary_changes[key] = {"left": left_summary.get(key), "right": right_summary.get(key)}
    return {
        "left_dataset_id": str(left.id), "right_dataset_id": str(right.id),
        "dataset_type": left.dataset_type, "scope_code": left.scope_code,
        "business_date": right.business_date.isoformat() if right.business_date else None,
        "added_count": len(added), "removed_count": len(removed),
        "changed_count": len(changed), "unchanged_count": len(set(left_rows) & set(right_rows)) - len(changed),
        "added_keys": added[:500], "removed_keys": removed[:500], "changed_keys": changed[:500],
        "summary_changes": summary_changes,
    }


def reject_dataset(session: Session, dataset: DatasetVersion, actor_id: str, reason: str) -> None:
    if dataset.status not in {ImportStatus.VALIDATED, ImportStatus.APPROVED}:
        raise ValueError("Отклонить можно только проверенный или утверждённый набор данных")
    # Unlike approve/confirm-mapping, self-review isn't blocked here on
    # purpose: a solo domain operator must be able to pull back their own
    # mistaken upload before it's ever published, without needing a second
    # person. The independent-review guarantee still applies to publishing
    # (approve_dataset), which is the step that actually matters.
    if not reason.strip(): raise ValueError("Требуется причина отклонения")
    dataset.status = ImportStatus.REJECTED
    dataset.rejection_reason = reason.strip()
    _audit(session, dataset, actor_id, "dataset.rejected", {"reason": reason.strip()})


def publish_dataset(
    session: Session,
    dataset: DatasetVersion,
    actor_id: str,
    *,
    source_first: bool = False,
) -> None:
    consumed_formula_audit = dataset.summary.get("consumed_formula_audit", {}) if isinstance(dataset.summary, dict) else {}
    if consumed_formula_audit.get("status") == "blocked":
        raise ValueError("Публикация заблокирована: используемые результаты формул пусты или содержат ошибку в исходной книге")
    if source_first:
        if dataset.status != ImportStatus.VALIDATED:
            raise ValueError("В режиме первичного источника публиковать можно только проверенный набор данных")
    elif dataset.status != ImportStatus.APPROVED:
        raise ValueError("Публиковать можно только независимо утверждённый набор данных")
    date_match = [DatasetVersion.business_date == dataset.business_date]
    if dataset.source_report_date is not None:
        date_match.append(DatasetVersion.source_report_date == dataset.source_report_date)
    prior = list(session.scalars(select(DatasetVersion).where(
        DatasetVersion.dataset_type == dataset.dataset_type,
        DatasetVersion.scope_code == dataset.scope_code,
        DatasetVersion.uploader_id == dataset.uploader_id,
        or_(*date_match),
        DatasetVersion.status == ImportStatus.PUBLISHED,
        DatasetVersion.id != dataset.id,
    )))
    for item in prior:
        item.status = ImportStatus.SUPERSEDED
        _audit(session, item, actor_id, "dataset.superseded", {"replacement_id": str(dataset.id)})
    # The published-version partial unique index must see the old row as
    # superseded before the replacement is marked published. This is required
    # on both SQLite and PostgreSQL and makes same-date corrections work.
    if prior:
        session.flush()
    dataset.status = ImportStatus.PUBLISHED
    dataset.publisher_id = actor_id
    dataset.published_at = utcnow()
    _audit(
        session,
        dataset,
        actor_id,
        "dataset.source_first_published" if source_first else "dataset.published",
        {"mode": "source_first"} if source_first else None,
    )
    session.flush()
    if dataset.scope_code in {"TABYS", "SAQ"}:
        reconcile_fund(session, dataset.scope_code)
    if dataset.dataset_type == "accounting_portfolio_detail":
        reconcile_accounting_portfolio(session, dataset)


def withdraw_dataset(session: Session, dataset: DatasetVersion, actor_id: str, reason: str) -> None:
    if dataset.status != ImportStatus.PUBLISHED:
        raise ValueError("Снять можно только опубликованный набор данных")
    # Deliberately not blocked for the uploader: re-uploading a corrected
    # file already supersedes a wrong publish automatically (see
    # publish_dataset), but a bad upload with no same-date replacement
    # still needs a way to come down without requiring a second person -
    # a solo domain operator must be able to do that themselves.
    if not reason.strip(): raise ValueError("Требуется причина снятия")
    dataset.status = ImportStatus.WITHDRAWN
    dataset.rejection_reason = reason.strip()
    _audit(session, dataset, actor_id, "dataset.withdrawn", {"reason": reason.strip()})


def record_dataset_event(session: Session, dataset: DatasetVersion, actor_id: str, action: str, detail: dict[str, Any] | None = None) -> None:
    """Record a PII-safe read/export event without logging record identifiers."""
    _audit(session, dataset, actor_id, action, detail or {})


def get_dataset(session: Session, dataset_id: UUID) -> DatasetVersion | None:
    return session.scalar(select(DatasetVersion).options(
        selectinload(DatasetVersion.source_upload), selectinload(DatasetVersion.records),
        selectinload(DatasetVersion.issues), selectinload(DatasetVersion.audit_events),
    ).where(DatasetVersion.id == dataset_id))


def list_datasets(session: Session, *, dataset_type: str | None = None, scope_code: str | None = None) -> list[DatasetVersion]:
    statement = select(DatasetVersion).options(selectinload(DatasetVersion.source_upload), selectinload(DatasetVersion.issues)).order_by(DatasetVersion.created_at.desc())
    if dataset_type: statement = statement.where(DatasetVersion.dataset_type == dataset_type)
    if scope_code: statement = statement.where(DatasetVersion.scope_code == scope_code.upper())
    items = list(session.scalars(statement))
    return _hide_demo_versions_when_source_loaded(items)


def latest_published(session: Session, dataset_type: str, scope_code: str, *, uploader_id: str | None = None) -> DatasetVersion | None:
    """The latest published dataset of this type/scope.

    ``uploader_id``, when given, scopes selection to one uploader's own
    version chain - a normal domain operator must see only their own
    uploads (docs/domain-upload-instructions.md "Visibility rule"), so the
    "current" dataset a module reads must be selected from that operator's
    own publishes, not the domain's newest publish regardless of who made
    it. Left unset for internal/system uses (reconciliation, cross-scope
    validation) that operate on canonical published state rather than a
    specific reader's view.
    """
    statement = select(DatasetVersion).options(
        selectinload(DatasetVersion.source_upload), selectinload(DatasetVersion.records), selectinload(DatasetVersion.issues)
    ).join(SourceUpload).where(
        DatasetVersion.dataset_type == dataset_type,
        DatasetVersion.scope_code == scope_code,
        DatasetVersion.status == ImportStatus.PUBLISHED,
    )
    if uploader_id is not None:
        statement = statement.where(DatasetVersion.uploader_id == uploader_id)
    return session.scalar(statement.order_by(
        # Local demo fixtures are useful before a real workbook is loaded, but
        # must never win over an imported source merely because their synthetic
        # business date is newer. Once a real source exists for this dataset
        # scope, all module widgets use that source consistently.
        _demo_order(),
        func.coalesce(DatasetVersion.source_report_date, DatasetVersion.business_date).desc().nullslast(),
        DatasetVersion.business_date.desc().nullslast(),
        DatasetVersion.version.desc(),
    ))


_RISK_PORTFOLIO_DATASET_TYPES = {"risk_limits_sobstv": "sobstv", "risk_limits_tabys": "tabys"}


def risk_trend_history(session: Session, *, uploader_id: str | None = None) -> list[dict[str, Any]]:
    """Breach/near-breach counts per published business date, both portfolios.

    Reuses each version's already-computed ``summary`` (breach_count/
    near_breach_count are set once at parse time - see _risk_summary in
    ingestion/multi_source.py) rather than re-scanning records, and applies
    the same uploader scoping as latest_published so a reader only ever
    sees their own publish history.
    """
    statement = select(DatasetVersion).where(
        DatasetVersion.dataset_type.in_(_RISK_PORTFOLIO_DATASET_TYPES),
        DatasetVersion.status == ImportStatus.PUBLISHED,
        DatasetVersion.business_date.is_not(None),
    )
    if uploader_id is not None:
        statement = statement.where(DatasetVersion.uploader_id == uploader_id)
    versions = list(session.scalars(statement.order_by(DatasetVersion.business_date.asc())))
    by_date: dict[date, dict[str, Any]] = {}
    for version in versions:
        portfolio = _RISK_PORTFOLIO_DATASET_TYPES[version.dataset_type]
        entry = by_date.setdefault(version.business_date, {"business_date": version.business_date.isoformat()})
        entry[portfolio] = {
            "breach_count": (version.summary or {}).get("breach_count", 0),
            "near_breach_count": (version.summary or {}).get("near_breach_count", 0),
        }
    history = sorted(by_date.values(), key=lambda entry: entry["business_date"])
    for entry in history:
        entry["breach_count"] = sum(entry.get(portfolio, {}).get("breach_count", 0) for portfolio in _RISK_PORTFOLIO_DATASET_TYPES.values())
        entry["near_breach_count"] = sum(entry.get(portfolio, {}).get("near_breach_count", 0) for portfolio in _RISK_PORTFOLIO_DATASET_TYPES.values())
    return history


def risk_utilization_history(session: Session, *, uploader_id: str | None = None) -> list[dict[str, Any]]:
    """Return source-derived utilization observations for comparable risk lines.

    A utilization ratio is only comparable with the *same* portfolio,
    dimension, and source label.  This deliberately returns observations at
    that grain instead of manufacturing a portfolio-wide utilization average
    from overlapping dimensions such as issuer, country, and sector.
    """
    statement = (
        select(DatasetVersion)
        .options(selectinload(DatasetVersion.records))
        .where(
            DatasetVersion.dataset_type.in_(_RISK_PORTFOLIO_DATASET_TYPES),
            DatasetVersion.status == ImportStatus.PUBLISHED,
            DatasetVersion.business_date.is_not(None),
        )
    )
    if uploader_id is not None:
        statement = statement.where(DatasetVersion.uploader_id == uploader_id)

    observations: list[dict[str, Any]] = []
    versions = session.scalars(statement.order_by(DatasetVersion.business_date.asc())).unique()
    for version in versions:
        portfolio = _RISK_PORTFOLIO_DATASET_TYPES[version.dataset_type]
        for record in version.records:
            if record.record_type != "risk_limit":
                continue
            payload = record.payload or {}
            dimension = str(payload.get("dimension") or "").strip()
            label = str(payload.get("label") or "").strip()
            try:
                utilization = Decimal(str(payload.get("utilization")))
            except (ArithmeticError, TypeError, ValueError):
                continue
            if not dimension or not label or utilization < 0:
                continue
            observations.append({
                "business_date": version.business_date.isoformat(),
                "portfolio_code": portfolio.upper(),
                "dimension": dimension,
                "label": label,
                # JSON must not receive Decimal.  A string keeps the parsed
                # source ratio exact until the browser renders it as a percent.
                "utilization": str(utilization),
            })
    return observations


# Condensed, management-style balance sheet: the full statutory f1_uip
# balance sheet (60+ line items) rolled up into the same 13-row grouping
# the budget workbook's own "БАЛАНС" section uses (see
# ingestion/multi_source/accounting.py's _parse_accounting_budget) - the
# exact grouping formulas came from a real internal rollup workbook,
# confirmed against a live f1_uip file (a separate, newer real workbook the
# rollup's own author maintains locally - read for its formulas only, never
# uploaded or persisted here). This is the bridge that lets an "actual vs.
# budget" comparison exist on the balance sheet at all, which the page's
# own AccountingComparabilityNotice already discloses is otherwise missing.
#
# Matched by line label, not line_code: the rollup workbook's own formulas
# reference f1_uip by fixed row number, but comparing that file's line
# codes against this app's currently-published balance sheet found the
# numbering itself isn't stable across workbook versions (e.g. "Итого
# обязательства" is code 42 in one, 43 in another) - only the label text
# is. Groups use "total minus the other named groups" rather than an
# enumerated residual list (mirroring the rollup's own liabilities line,
# B10=f1_uip!C109-B9) precisely because that's immune to the same
# renumbering, and to a workbook adding or removing a granular line inside
# an existing group. Restricted to top-level line codes (no "." in the
# code, e.g. "1" but not "1.1") - a dotted code is always a breakdown of
# its own parent line, already counted once there; including it too would
# double it.
_CONDENSED_BALANCE_SHEET_LINES: tuple[tuple[str, str, str], ...] = (
    ("asset", "Денежные средства", "Денежные средства"),
    ("asset", "Средства, размещённые в других банках и операции «обратное РЕПО»", "Cash placed with other banks and reverse repo"),
    ("asset", "Инвестиционный портфель", "Investment portfolio"),
    ("asset", "Основные средства и НМА", "Fixed assets and intangibles"),
    ("asset", "Прочие активы", "Other assets"),
    ("liability", "Привлечённые средства от банков и финансовых институтов", "Borrowings from banks and financial institutions"),
    ("liability", "Прочие обязательства", "Other liabilities"),
    ("equity", "Уставный капитал", "Share capital"),
    ("equity", "Резерв переоценки ЦБ", "Securities revaluation reserve"),
    ("equity", "Нераспределённая прибыль", "Retained earnings"),
)


# Human-readable matcher descriptions for each sum_matching-based row, kept
# alongside the predicates below rather than reverse-engineered from them in
# the frontend - the derivation drawer quotes these verbatim.
_ROW_MATCHER_TEXT: dict[str, tuple[str, str]] = {
    "Денежные средства": (
        "Наименование строки равно «Денежные средства», «Вклады размещенные» или «Вклады размещённые».",
        'Line label equals "Денежные средства", "Вклады размещенные", or "Вклады размещённые".',
    ),
    "Средства, размещённые в других банках и операции «обратное РЕПО»": (
        "Наименование строки содержит «репо».",
        'Line label contains "репо" (repo).',
    ),
    "Инвестиционный портфель": (
        "Наименование строки содержит «ценные бумаги» либо равно «Производные финансовые инструменты».",
        'Line label contains "ценные бумаги" (securities) or equals "Производные финансовые инструменты" (derivatives).',
    ),
    "Основные средства и НМА": (
        "Наименование строки равно «Нематериальные активы», «Гудвилл» или «Основные средства».",
        'Line label equals "Нематериальные активы", "Гудвилл", or "Основные средства".',
    ),
    "Привлечённые средства от банков и финансовых институтов": (
        "Наименование строки равно «Займы полученные».",
        'Line label equals "Займы полученные" (borrowings received).',
    ),
    "Уставный капитал": (
        "Наименование строки равно «Уставный капитал».",
        'Line label equals "Уставный капитал" (share capital).',
    ),
    "Резерв переоценки ЦБ": (
        "Наименование строки содержит «резерв переоценки» или «резерв обесценения».",
        'Line label contains "резерв переоценки" or "резерв обесценения" (revaluation/impairment reserve).',
    ),
    "Нераспределённая прибыль": (
        "Наименование строки содержит «нераспределенная прибыль» (в любом написании).",
        'Line label contains "нераспределенная прибыль" (retained earnings), either spelling.',
    ),
}


def _contributing_line(row: dict[str, Any], *, sign: str = "+") -> dict[str, Any]:
    """A single raw balance-sheet line feeding a rollup row's sum.

    Carries the record's own id/source_ref when the caller passed the full
    module_payload-enriched dicts (web) so the frontend can open a cell
    preview; the Excel export path only ever passes bare payload dicts, so
    these stay None there - harmless, since the workbook already sits next
    to every other sheet in that file.
    """
    return {
        "kind": "line",
        "sign": sign,
        "line_code": row.get("line_code"),
        "line_label": row.get("line_label"),
        "current_period_kzt": row.get("current_period_kzt"),
        "prior_period_kzt": row.get("prior_period_kzt"),
        "id": row.get("id"),
        "source": row.get("source"),
    }


def _contributing_row(label_ru: str, label_en: str, value: tuple[Decimal | None, Decimal | None], *, sign: str = "+") -> dict[str, Any]:
    """A reference to another already-computed rollup row (not a raw source
    line) - used when a total is built from rows above rather than by
    matching source lines directly, e.g. ИТОГО СОБСТВЕННЫЙ КАПИТАЛ."""
    current, prior = value
    return {
        "kind": "row", "sign": sign, "label_ru": label_ru, "label_en": label_en,
        "current_period_kzt": str(current) if current is not None else None,
        "prior_period_kzt": str(prior) if prior is not None else None,
    }


def condensed_balance_sheet(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Roll up the full balance sheet into the budget's own 13-row grouping.

    Every returned row carries a "derivation" describing exactly how its
    value was built - which source lines (or, for a total built from rows
    above, which other rollup rows) contributed, with what sign, plus a
    human-readable matcher description - so a reviewer can see the full
    chain from a rollup figure back to the source workbook.
    """
    top_level = [r for r in records if "." not in str(r.get("line_code") or "")]

    def section_rows(section: str) -> list[dict[str, Any]]:
        return [r for r in top_level if str(r.get("section") or "").casefold() == section.casefold()]

    def sum_matching(rows: list[dict[str, Any]], predicate) -> tuple[Decimal, Decimal, list[dict[str, Any]]]:
        # Zero (not None/unavailable) when nothing matches: a bucket with no
        # corresponding line item this period is a legitimately empty
        # bucket (e.g. no deposits placed), the same way an unfilled
        # section of a form means "none", not "unknown". This also lets
        # the equity reconciliation check below actually flag a gap - a
        # bucket that quietly turned "unavailable" instead of "0" would
        # poison the whole total to None and hide the mismatch instead of
        # surfacing it.
        current = Decimal(0)
        prior = Decimal(0)
        matched: list[dict[str, Any]] = []
        for row in rows:
            label = str(row.get("line_label") or "").strip().casefold()
            if not predicate(label):
                continue
            matched.append(row)
            row_current = row.get("current_period_kzt")
            row_prior = row.get("prior_period_kzt")
            if row_current is not None:
                current += Decimal(str(row_current))
            if row_prior is not None:
                prior += Decimal(str(row_prior))
        return current, prior, matched

    def total_line(rows: list[dict[str, Any]], label: str) -> tuple[Decimal | None, Decimal | None, dict[str, Any] | None]:
        for row in rows:
            if str(row.get("line_label") or "").strip().casefold() == label:
                current = row.get("current_period_kzt")
                prior = row.get("prior_period_kzt")
                return (Decimal(str(current)) if current is not None else None, Decimal(str(prior)) if prior is not None else None, row)
        return None, None, None

    def minus(total: tuple[Decimal | None, Decimal | None], *parts: tuple[Decimal | None, Decimal | None]) -> tuple[Decimal | None, Decimal | None]:
        total_current, total_prior = total
        if total_current is None or total_prior is None:
            return None, None
        current, prior = total_current, total_prior
        for part_current, part_prior in parts:
            current -= part_current or Decimal(0)
            prior -= part_prior or Decimal(0)
        return current, prior

    assets = section_rows("Активы")
    liabilities = section_rows("Обязательства")
    equity = section_rows("Собственный капитал")

    cash_c, cash_p, cash_lines = sum_matching(assets, lambda label: label in ("денежные средства", "вклады размещенные", "вклады размещённые"))
    repo_c, repo_p, repo_lines = sum_matching(assets, lambda label: "репо" in label)
    portfolio_c, portfolio_p, portfolio_lines = sum_matching(assets, lambda label: "ценные бумаги" in label or label == "производные финансовые инструменты")
    fixed_c, fixed_p, fixed_lines = sum_matching(assets, lambda label: label in ("нематериальные активы", "гудвилл", "основные средства"))
    cash, repo, portfolio, fixed_assets = (cash_c, cash_p), (repo_c, repo_p), (portfolio_c, portfolio_p), (fixed_c, fixed_p)
    total_assets_c, total_assets_p, total_assets_line = total_line(assets, "итого активы")
    total_assets = (total_assets_c, total_assets_p)
    other_assets = minus(total_assets, cash, repo, portfolio, fixed_assets)

    loans_c, loans_p, loans_lines = sum_matching(liabilities, lambda label: label == "займы полученные")
    loans = (loans_c, loans_p)
    total_liabilities_c, total_liabilities_p, total_liabilities_line = total_line(liabilities, "итого обязательства")
    total_liabilities = (total_liabilities_c, total_liabilities_p)
    other_liabilities = minus(total_liabilities, loans)

    share_c, share_p, share_lines = sum_matching(equity, lambda label: label == "уставный капитал")
    reval_c, reval_p, reval_lines = sum_matching(equity, lambda label: "резерв переоценки" in label or "резерв обесценения" in label)
    retained_c, retained_p, retained_lines = sum_matching(equity, lambda label: "нераспределенная прибыль" in label or "нераспределённая прибыль" in label)
    share_capital, revaluation_reserve, retained_earnings = (share_c, share_p), (reval_c, reval_p), (retained_c, retained_p)

    values: dict[str, tuple[tuple[Decimal, Decimal], list[dict[str, Any]]]] = {
        "Денежные средства": (cash, cash_lines),
        "Средства, размещённые в других банках и операции «обратное РЕПО»": (repo, repo_lines),
        "Инвестиционный портфель": (portfolio, portfolio_lines),
        "Основные средства и НМА": (fixed_assets, fixed_lines),
        "Привлечённые средства от банков и финансовых институтов": (loans, loans_lines),
        "Уставный капитал": (share_capital, share_lines),
        "Резерв переоценки ЦБ": (revaluation_reserve, reval_lines),
        "Нераспределённая прибыль": (retained_earnings, retained_lines),
    }

    def as_str(value: Decimal | None) -> str | None:
        return str(value) if value is not None else None

    # Equity has no source residual (the rollup workbook sums exactly these
    # three named lines, unlike assets/liabilities' "total minus" design) -
    # sum them directly rather than subtracting from "Итого капитал", so a
    # nonzero balance on some other equity line (e.g. a reserve this
    # workbook doesn't carry today) shows up as a real reconciliation gap
    # instead of being silently absorbed into "Нераспределённая прибыль".
    def add(*parts: tuple[Decimal | None, Decimal | None]) -> tuple[Decimal | None, Decimal | None]:
        current = Decimal(0)
        prior = Decimal(0)
        for part_current, part_prior in parts:
            if part_current is None or part_prior is None:
                return None, None
            current += part_current
            prior += part_prior
        return current, prior

    total_equity_computed = add(share_capital, revaluation_reserve, retained_earnings)
    total_equity_source_c, total_equity_source_p, total_equity_source_line = total_line(equity, "итого капитал")
    total_equity_source = (total_equity_source_c, total_equity_source_p)

    rows: list[dict[str, Any]] = []
    for group, label_ru, label_en in _CONDENSED_BALANCE_SHEET_LINES:
        if label_ru == "Прочие активы":
            other_assets_c, other_assets_p = other_assets
            derivation = {
                "kind": "total_minus_lines",
                "formula_ru": "Итого активы − (Денежные средства + РЕПО/обратное РЕПО + Инвестиционный портфель + Основные средства и НМА)",
                "formula_en": "Total assets − (Cash + Repo/reverse repo + Investment portfolio + Fixed assets and intangibles)",
                "contributors": [
                    (_contributing_line(total_assets_line, sign="+") if total_assets_line else {"kind": "line", "sign": "+", "line_code": None, "line_label": "Итого активы", "current_period_kzt": as_str(total_assets_c), "prior_period_kzt": as_str(total_assets_p), "id": None, "source": None}),
                    _contributing_row("Денежные средства", "Денежные средства", cash, sign="-"),
                    _contributing_row("Средства, размещённые в других банках и операции «обратное РЕПО»", "Cash placed with other banks and reverse repo", repo, sign="-"),
                    _contributing_row("Инвестиционный портфель", "Investment portfolio", portfolio, sign="-"),
                    _contributing_row("Основные средства и НМА", "Fixed assets and intangibles", fixed_assets, sign="-"),
                ],
            }
            rows.append({"group": group, "is_total": False, "label_ru": label_ru, "label_en": label_en, "current_period_kzt": as_str(other_assets_c), "prior_period_kzt": as_str(other_assets_p), "derivation": derivation})
            # Not a "reconciles" field here: total_assets IS the source's own
            # "Итого активы" line, and "Прочие активы" was derived as
            # total_assets minus the other four groups - the two can never
            # disagree by construction, unlike equity below.
            rows.append({
                "group": "total", "is_total": True, "label_ru": "ИТОГО АКТИВЫ", "label_en": "TOTAL ASSETS",
                "current_period_kzt": as_str(total_assets_c), "prior_period_kzt": as_str(total_assets_p),
                "derivation": {
                    "kind": "source_total_line",
                    "formula_ru": 'Значение читается напрямую из строки источника «Итого активы» (лист f1_uip) - не пересчитывается.',
                    "formula_en": 'Read directly from the source workbook\'s own "Итого активы" line (sheet f1_uip) - not recomputed.',
                    "contributors": [_contributing_line(total_assets_line)] if total_assets_line else [],
                },
            })
            continue
        if label_ru == "Прочие обязательства":
            other_liabilities_c, other_liabilities_p = other_liabilities
            derivation = {
                "kind": "total_minus_lines",
                "formula_ru": "Итого обязательства − Займы полученные",
                "formula_en": "Total liabilities − Borrowings received",
                "contributors": [
                    (_contributing_line(total_liabilities_line, sign="+") if total_liabilities_line else {"kind": "line", "sign": "+", "line_code": None, "line_label": "Итого обязательства", "current_period_kzt": as_str(total_liabilities_c), "prior_period_kzt": as_str(total_liabilities_p), "id": None, "source": None}),
                    _contributing_row("Привлечённые средства от банков и финансовых институтов", "Borrowings from banks and financial institutions", loans, sign="-"),
                ],
            }
            rows.append({"group": group, "is_total": False, "label_ru": label_ru, "label_en": label_en, "current_period_kzt": as_str(other_liabilities_c), "prior_period_kzt": as_str(other_liabilities_p), "derivation": derivation})
            rows.append({
                "group": "total", "is_total": True, "label_ru": "ИТОГО ОБЯЗАТЕЛЬСТВА", "label_en": "TOTAL LIABILITIES",
                "current_period_kzt": as_str(total_liabilities_c), "prior_period_kzt": as_str(total_liabilities_p),
                "derivation": {
                    "kind": "source_total_line",
                    "formula_ru": 'Значение читается напрямую из строки источника «Итого обязательства» (лист f1_uip) - не пересчитывается.',
                    "formula_en": 'Read directly from the source workbook\'s own "Итого обязательства" line (sheet f1_uip) - not recomputed.',
                    "contributors": [_contributing_line(total_liabilities_line)] if total_liabilities_line else [],
                },
            })
            continue
        value, matched_lines = values[label_ru]
        current, prior = value
        matcher_ru, matcher_en = _ROW_MATCHER_TEXT[label_ru]
        rows.append({
            "group": group, "is_total": False, "label_ru": label_ru, "label_en": label_en,
            "current_period_kzt": as_str(current), "prior_period_kzt": as_str(prior),
            "derivation": {
                "kind": "sum_of_lines",
                "formula_ru": f"Сумма строк раздела Баланса, для которых: {matcher_ru}",
                "formula_en": f"Sum of Balance Sheet lines where: {matcher_en}",
                "contributors": [_contributing_line(row) for row in matched_lines],
            },
        })
        if label_ru == "Нераспределённая прибыль":
            equity_current, equity_prior = total_equity_computed
            source_current, source_prior = total_equity_source
            rows.append({
                "group": "total", "is_total": True, "label_ru": "ИТОГО СОБСТВЕННЫЙ КАПИТАЛ", "label_en": "TOTAL EQUITY",
                "current_period_kzt": as_str(equity_current), "prior_period_kzt": as_str(equity_prior),
                "reconciles": total_equity_computed == total_equity_source,
                "derivation": {
                    "kind": "sum_of_rows_above",
                    "formula_ru": "Уставный капитал + Резерв переоценки ЦБ + Нераспределённая прибыль",
                    "formula_en": "Share capital + Securities revaluation reserve + Retained earnings",
                    "contributors": [
                        _contributing_row("Уставный капитал", "Share capital", share_capital),
                        _contributing_row("Резерв переоценки ЦБ", "Securities revaluation reserve", revaluation_reserve),
                        _contributing_row("Нераспределённая прибыль", "Retained earnings", retained_earnings),
                    ],
                    "source_total_line": _contributing_line(total_equity_source_line) if total_equity_source_line else None,
                    "source_total_current_period_kzt": as_str(source_current),
                    "source_total_prior_period_kzt": as_str(source_prior),
                },
            })
    return rows


_ACCOUNT_CODE_DATASET_TYPES = ("accounting_balance_sheet", "accounting_income_statement")


def account_code_registry(session: Session, dataset_type: str, *, uploader_id: str | None = None) -> list[dict[str, Any]]:
    """Line-code identity and label-drift derived from published workbooks.

    There is no external chart of accounts to import against - line_code is
    the only durable identity a balance-sheet/income-statement row carries
    across periods, so this registry is derived purely from what has
    actually been published, not from a separately curated dictionary. A
    code is flagged with ``label_drift`` when the same code has carried more
    than one distinct label across published periods, which is exactly the
    ambiguity a period comparison (Accounting #2/#3) must not silently paper
    over. ``is_new`` marks a code that only exists in the most recent
    published version, scoped by uploader like every other accounting read.
    """
    if dataset_type not in _ACCOUNT_CODE_DATASET_TYPES:
        return []
    statement = select(DatasetVersion).options(selectinload(DatasetVersion.records)).where(
        DatasetVersion.dataset_type == dataset_type,
        DatasetVersion.status == ImportStatus.PUBLISHED,
    )
    if uploader_id is not None:
        statement = statement.where(DatasetVersion.uploader_id == uploader_id)
    versions = list(session.scalars(statement.order_by(
        func.coalesce(DatasetVersion.source_report_date, DatasetVersion.business_date).asc().nullslast(),
        DatasetVersion.version.asc(),
    )))
    if not versions:
        return []
    latest_version_id = versions[-1].id
    latest_period = (versions[-1].source_report_date or versions[-1].business_date)
    latest_period_text = latest_period.isoformat() if latest_period else None
    by_code: dict[str, dict[str, Any]] = {}
    for version in versions:
        period = (version.source_report_date or version.business_date)
        period_text = period.isoformat() if period else None
        seen_this_version: set[str] = set()
        for record in version.records:
            code = record.payload.get("line_code")
            label = record.payload.get("line_label")
            if not code or not label or code in seen_this_version:
                continue
            seen_this_version.add(code)
            entry = by_code.setdefault(code, {"line_code": code, "section": record.payload.get("section"), "labels": [], "first_seen": period_text, "last_seen": period_text, "seen_in_latest": False})
            entry["last_seen"] = period_text or entry["last_seen"]
            entry["section"] = record.payload.get("section") or entry["section"]
            entry["seen_in_latest"] = version.id == latest_version_id
            if not entry["labels"] or entry["labels"][-1]["label"] != label:
                entry["labels"].append({"label": label, "first_seen": period_text})
    registry = []
    for entry in by_code.values():
        # "New" only means something once there is a prior period to compare
        # against - a code present since the very first published version is
        # not "new", it is simply the whole known history for that code.
        is_new = len(versions) > 1 and entry["first_seen"] == latest_period_text and entry["seen_in_latest"]
        registry.append({
            "line_code": entry["line_code"],
            "section": entry["section"],
            "current_label": entry["labels"][-1]["label"] if entry["labels"] else None,
            "first_seen": entry["first_seen"],
            "last_seen": entry["last_seen"],
            "label_history": entry["labels"],
            "label_drift": len(entry["labels"]) > 1,
            "is_new": is_new,
        })
    registry.sort(key=lambda item: item["line_code"])
    return registry


# Every dataset_type this app parses from an uploaded workbook, grouped by
# how often that workbook is realistically expected to be re-uploaded. There
# is no confirmed cadence policy yet (docs/todo.md's open-decisions list
# still asks "what refresh cadence is required per domain"), so these are
# explicit, disclosed starting defaults - not a guessed fact - versioned via
# READINESS_SLA_VERSION so a future policy change is auditable, exactly like
# RISK_NEAR_BREACH_THRESHOLD.
READINESS_SLA_VERSION = "v1"
_READINESS_SLA_DAYS: dict[str, int] = {
    "risk_limits_sobstv": 3, "risk_limits_tabys": 3,
    "fund_valuation": 3, "fund_holdings": 3, "fund_cash_liabilities": 3,
    "fund_nav_history": 3, "fund_prices": 3, "fund_unit_series": 3, "fund_inactive_evidence": 3,
    "brokerage_trade_ledger": 3, "derivatives_register": 3,
    "client_account_snapshot": 3, "client_open_dates": 3, "client_maturity_calendar": 3, "client_dashboard_snapshot": 3,
    "corporate_finance_register": 30,
    "accounting_landing": 35, "accounting_balance_sheet": 35, "accounting_income_statement": 35,
    "accounting_budget": 35, "accounting_portfolio_detail": 35,
}
_READINESS_SLA_DEFAULT_DAYS = 7


def readiness_register(session: Session, *, uploader_id: str | None = None) -> list[dict[str, Any]]:
    """One row per dataset_type/scope this uploader currently owns.

    Reuses the same uploader-scoped ``latest_published`` every domain page
    already reads from, so this register never shows a dataset the reader
    couldn't otherwise see. ``status`` combines freshness against an
    explicit SLA with whether the current version has an unresolved
    blocker-severity DQ finding - a fresh version with a blocker is still
    "blocked", never reported as ready.
    """
    seen: set[tuple[str, str]] = set()
    entries: list[dict[str, Any]] = []
    for module_types in _all_dataset_type_scopes().values():
        for dataset_type, scope in module_types:
            if (dataset_type, scope) in seen:
                continue
            seen.add((dataset_type, scope))
            dataset = latest_published(session, dataset_type, scope, uploader_id=uploader_id)
            sla_days = _READINESS_SLA_DAYS.get(dataset_type, _READINESS_SLA_DEFAULT_DAYS)
            if dataset is None:
                entries.append({
                    "dataset_type": dataset_type, "scope_code": scope, "business_date": None,
                    "sla_days": sla_days, "dq_blocker_count": 0, "dq_high_count": 0, "status": "missing",
                })
                continue
            blockers = sum(issue.severity == "blocker" for issue in dataset.issues)
            highs = sum(issue.severity == "high" for issue in dataset.issues)
            entries.append({
                "dataset_type": dataset_type, "scope_code": scope,
                "business_date": dataset.business_date.isoformat() if dataset.business_date else None,
                "sla_days": sla_days, "dq_blocker_count": blockers, "dq_high_count": highs,
                "status": _readiness_status(dataset.business_date, sla_days, blockers),
            })
    entries.sort(key=lambda item: (item["status"] != "blocked", item["status"] != "overdue", item["dataset_type"]))
    return entries


def _readiness_status(business_date: date | None, sla_days: int, blocker_count: int) -> str:
    if business_date is None:
        return "blocked" if blocker_count else "unavailable"
    # date.today(), not utcnow().date(): this app runs on a machine
    # configured for the business's own timezone (this is a local,
    # single-instance tool, not a distributed UTC-everywhere service - see
    # services/dividends.py, which already uses date.today() for the same
    # reason). Kazakhstan is UTC+5/+6, so utcnow().date() lags the real
    # local date for several hours every night - confirmed on the actual
    # deployment machine (date +%Z reports +05). Using it here would
    # silently under-count every age/staleness/overdue check by a day
    # during that window.
    age = (date.today() - business_date).days
    if blocker_count:
        return "blocked"
    if age < 0 or age <= sla_days:
        return "ready"
    if age <= sla_days * 2:
        return "due"
    return "overdue"


def _all_dataset_type_scopes() -> dict[str, list[tuple[str, str]]]:
    return {
        "asset-management": [("fund_valuation", "TABYS"), ("fund_holdings", "TABYS"), ("fund_cash_liabilities", "TABYS"), ("fund_nav_history", "TABYS"), ("fund_prices", "TABYS"), ("fund_unit_series", "TABYS"), ("fund_unit_series", "SAQ"), ("fund_inactive_evidence", "TABYS")],
        "brokerage": [("brokerage_trade_ledger", "BROKERAGE"), ("derivatives_register", "BROKERAGE"), ("client_account_snapshot", "BROKERAGE"), ("client_open_dates", "BROKERAGE"), ("client_maturity_calendar", "BROKERAGE"), ("client_dashboard_snapshot", "BROKERAGE")],
        "corporate-finance": [("corporate_finance_register", "CORPFIN")],
        "accounting": [("accounting_landing", "ACCOUNTING"), ("accounting_balance_sheet", "ACCOUNTING"), ("accounting_income_statement", "ACCOUNTING"), ("accounting_budget", "ACCOUNTING"), ("accounting_portfolio_detail", "ACCOUNTING")],
        "risk": [("risk_limits_sobstv", "SOBSTV"), ("risk_limits_tabys", "TABYS")],
    }


def _is_demo_source(upload: SourceUpload | None) -> bool:
    return bool(upload and upload.original_filename.casefold().startswith("demo_"))


def _demo_order():
    """SQL expression that sorts imported sources ahead of demo fixtures."""
    from sqlalchemy import case

    return case((SourceUpload.original_filename.ilike("demo_%"), 1), else_=0)


def _hide_demo_versions_when_source_loaded(items: list[DatasetVersion]) -> list[DatasetVersion]:
    """Keep the operational registry source-backed once a real file is loaded.

    Demo rows remain visible when they are the only available fixture, which
    keeps a fresh local install usable. For a scope with a real uploaded file,
    its synthetic demo siblings are hidden from default readiness/registry
    reads but remain immutable audit evidence in the database.
    """
    real_keys = {
        (item.dataset_type, item.scope_code)
        for item in items
        if not _is_demo_source(item.source_upload)
    }
    return [
        item
        for item in items
        if not _is_demo_source(item.source_upload)
        or (item.dataset_type, item.scope_code) not in real_keys
    ]


def module_payload(
    session: Session,
    module: str,
    language: str = "ru",
    version_overrides: dict[str, DatasetVersion] | None = None,
    source_upload_id: UUID | None = None,
    uploader_id: str | None = None,
) -> dict[str, Any]:
    if module == "treasury":
        batch_statement = select(ImportBatch).options(
            selectinload(ImportBatch.snapshot), selectinload(ImportBatch.source_upload)
        ).where(
            ImportBatch.portfolio_code == "SOBSTV",
            ImportBatch.status.in_((ImportStatus.PUBLISHED, ImportStatus.SUPERSEDED)) if source_upload_id is not None else ImportBatch.status == ImportStatus.PUBLISHED,
        )
        if uploader_id is not None:
            batch_statement = batch_statement.where(ImportBatch.uploader_id == uploader_id)
        if source_upload_id is not None:
            batch_statement = batch_statement.where(ImportBatch.source_upload_id == source_upload_id)
        batch = session.scalar(batch_statement.order_by(ImportBatch.report_date.desc(), ImportBatch.version.desc()))
        if batch is None or batch.snapshot is None:
            return {"module": module, "available": False, "report_date_mismatch": False, "filename_date_mismatch": False, "report_dates": [], "sources": [], "summaries": {}, "records": {}, "disclosure": localize_text("Операционные/расчётные данные портфеля; не официальный NAV или рыночная стоимость.", language), "selected_source_upload_id": str(source_upload_id) if source_upload_id else None}
        snapshot = batch.snapshot
        source = batch.source_upload
        source_date = batch.source_report_date or snapshot.report_date
        business_date = batch.business_date or snapshot.report_date
        dates = sorted({source_date.isoformat(), business_date.isoformat()})
        source_filename = source.original_filename if source else batch.original_filename
        return {
            "module": module, "available": True, "report_date_mismatch": len(dates) > 1,
            "filename_date_mismatch": filename_date_mismatch(source_filename, source_date),
            "report_dates": dates,
            "sources": [{"dataset_id": str(batch.id), "source_upload_id": str(batch.source_upload_id), "dataset_type": "portfolio_snapshot", "scope_type": "portfolio", "scope_code": "SOBSTV", "source_filename": source_filename, "source_report_date": source_date.isoformat(), "business_date": business_date.isoformat(), "version": snapshot.version, "status": batch.status.value, "generated_at": batch.generated_at.isoformat() if batch.generated_at else None, "parser_version": batch.parser_version, "freshness": _freshness(business_date), "dq_blocker_count": sum(issue.severity == "blocker" for issue in snapshot.issues), "dq_high_count": sum(issue.severity == "high" for issue in snapshot.issues)}],
            "summaries": {"portfolio_snapshot": {"snapshot_id": str(snapshot.id), "position_count": snapshot.position_count, "unique_isin_count": snapshot.unique_isin_count, "purchase_amount_kzt": str(snapshot.purchase_amount_kzt), "derived_carrying_value_kzt": str(snapshot.derived_carrying_value_kzt), "cash_kzt": str(snapshot.cash_kzt), "derived_operational_total_kzt": str(snapshot.derived_operational_total_kzt)}},
            "records": {}, "disclosure": localize_text("Операционные/расчётные данные портфеля; не официальный NAV или рыночная стоимость.", language),
            "selected_source_upload_id": str(source_upload_id) if source_upload_id else None,
            "pinned_dataset_types": ["portfolio_snapshot"] if source_upload_id else [],
        }
    type_map = {
        "asset-management": [("fund_valuation", "TABYS"), ("fund_holdings", "TABYS"), ("fund_cash_liabilities", "TABYS"), ("fund_nav_history", "TABYS"), ("fund_prices", "TABYS"), ("fund_unit_series", "TABYS"), ("fund_inactive_evidence", "TABYS")],
        "brokerage": [("brokerage_trade_ledger", "BROKERAGE"), ("derivatives_register", "BROKERAGE"), ("client_account_snapshot", "BROKERAGE"), ("client_maturity_calendar", "BROKERAGE"), ("client_dashboard_snapshot", "BROKERAGE")],
        "clients": [("client_account_snapshot", "BROKERAGE"), ("client_open_dates", "BROKERAGE"), ("client_maturity_calendar", "BROKERAGE"), ("client_dashboard_snapshot", "BROKERAGE")],
        "corporate-finance": [("corporate_finance_register", "CORPFIN")],
        "accounting": [("accounting_landing", "ACCOUNTING")],
        # Two distinct dataset_types, not one type shared across two scopes -
        # the per-dataset_type dicts built below (records/summaries) would
        # silently let the second-fetched portfolio overwrite the first if
        # both used the same dataset_type key.
        "risk": [("risk_limits_sobstv", "SOBSTV"), ("risk_limits_tabys", "TABYS")],
    }
    overrides = version_overrides or {}
    expected_types = [dataset_type for dataset_type, _ in type_map.get(module, [])]
    # The modules operated from one local workbook must always read a coherent
    # physical package.  Even the default "Current (latest)" state therefore
    # anchors on the latest primary child and loads its siblings from the same
    # source upload.  Asset Management deliberately keeps its established
    # cross-source view because valuation and unit-history workbooks are
    # independent feeds.
    package_modules = {"brokerage", "clients", "corporate-finance", "accounting"}
    effective_source_upload_id = source_upload_id
    if effective_source_upload_id is None and not overrides and module in package_modules and expected_types:
        anchor_type, anchor_scope = type_map[module][0]
        anchor = latest_published(session, anchor_type, anchor_scope, uploader_id=uploader_id)
        if anchor is not None:
            effective_source_upload_id = anchor.source_upload_id
    if effective_source_upload_id is not None:
        # One source upload is one coherent local-domain version.  The
        # brokerage workbook, for example, creates several child datasets;
        # they must be read together rather than independently pinned.
        uploaded = list(session.scalars(
            select(DatasetVersion).options(
                selectinload(DatasetVersion.source_upload),
                selectinload(DatasetVersion.records),
                selectinload(DatasetVersion.issues),
            ).where(
                DatasetVersion.source_upload_id == effective_source_upload_id,
                DatasetVersion.dataset_type.in_(expected_types),
                DatasetVersion.status.in_([ImportStatus.PUBLISHED, ImportStatus.SUPERSEDED]),
            )
        ))
        # Keyed by (dataset_type, scope_code), not dataset_type alone: one
        # source upload can produce several DatasetVersion rows sharing a
        # dataset_type under different scopes (TABYS's own fund_unit_series
        # rows exist for both the "TABYS" and "SAQ" scope from the same
        # workbook) or several re-materialized versions of the same scope.
        # A dataset_type-only key silently collapsed those into one -
        # non-deterministically picking whichever row the query happened to
        # return last, sometimes the wrong scope's data entirely (e.g. a
        # stale/inactive SAQ series shown - or dropped - in place of TABYS's
        # real one) - keep the highest ``version`` per (type, scope) instead.
        by_type_scope: dict[tuple[str, str], DatasetVersion] = {}
        for item in uploaded:
            key = (item.dataset_type, item.scope_code)
            current = by_type_scope.get(key)
            if current is None or item.version > current.version:
                by_type_scope[key] = item
        datasets = [by_type_scope[key] for key in type_map.get(module, []) if key in by_type_scope]
        covered_types = {dataset_type for dataset_type, _ in by_type_scope}
        # A dataset_type the pinned package doesn't cover isn't necessarily
        # unavailable - it may belong to a genuinely independent workbook
        # (Asset Management's fund_unit_series next to the pinned valuation
        # package) that the caller pinned separately via its own override.
        # Only dataset_types still missing after this stay "missing".
        for dataset_type in expected_types:
            if dataset_type in covered_types:
                continue
            override = overrides.get(dataset_type)
            if override is not None:
                datasets.append(override)
                covered_types.add(dataset_type)
        # "Pinned" is a user action, not the normal coherent-current view.
        pinned_dataset_types = [item.dataset_type for item in datasets] if (source_upload_id is not None or overrides) else []
        missing_source_dataset_types = [dataset_type for dataset_type in expected_types if dataset_type not in covered_types]
    else:
        datasets = [
            item for dataset_type, scope in type_map.get(module, [])
            if (item := overrides.get(dataset_type) or latest_published(session, dataset_type, scope, uploader_id=uploader_id))
        ]
        pinned_dataset_types = [dataset_type for dataset_type, _ in type_map.get(module, []) if dataset_type in overrides]
        missing_source_dataset_types = []
    if module == "accounting" and not datasets and source_upload_id is None:
        landing_statement = select(DatasetVersion).options(selectinload(DatasetVersion.source_upload), selectinload(DatasetVersion.records), selectinload(DatasetVersion.issues)).where(DatasetVersion.dataset_type == "accounting_landing")
        if uploader_id is not None:
            landing_statement = landing_statement.where(DatasetVersion.uploader_id == uploader_id)
        datasets = list(session.scalars(landing_statement.order_by(DatasetVersion.created_at.desc())))
    statement_datasets: list[DatasetVersion] = []
    if module == "accounting":
        # The balance sheet / income statement / budget-detail / portfolio-
        # detail each come from their own independent workbook, not
        # whichever budget/portfolio landing file happens to be anchoring
        # the package - they must show up whenever published, not only
        # when they happen to share a source_upload_id with the
        # accounting_landing anchor (see type_map's accounting entry).
        for statement_type in ("accounting_balance_sheet", "accounting_income_statement", "accounting_budget", "accounting_portfolio_detail"):
            statement_item = overrides.get(statement_type) or latest_published(session, statement_type, "ACCOUNTING", uploader_id=uploader_id)
            if statement_item is not None:
                statement_datasets.append(statement_item)
            if statement_type in overrides:
                # These four types aren't in type_map["accounting"] (only
                # accounting_landing is - see the comment above), so the
                # pinned_dataset_types computed above never sees them; each
                # is independently uploaded and pinned, same as the four
                # types themselves are independently fetched.
                pinned_dataset_types.append(statement_type)
        datasets = datasets + statement_datasets
    # ``business_date`` is operational for some feeds (for example, the
    # brokerage ledger uses the latest transaction date).  It must not make a
    # healthy workbook appear to have conflicting report dates.  Period-end
    # datasets are also deliberately excluded from this cross-source check;
    # their period-end date is a reporting label, not a second workbook date.
    # risk_limits_sobstv/tabys are two independently-published portfolios'
    # own workbooks (unlike accounting's balance sheet/income statement/
    # budget/portfolio detail, which really are meant to be as-of the same
    # company reporting date even though they're separate files) - SOBSTV
    # and TABYS are uploaded and published on their own schedules, so a
    # different business date between them is normal, not a data problem.
    comparable_datasets = [
        item for item in datasets
        if item.dataset_type not in ("derivatives_register", "risk_limits_sobstv", "risk_limits_tabys")
        and (item.summary or {}).get("date_basis") != "reporting_period_end"
    ]
    dates = sorted({
        value.isoformat()
        for item in comparable_datasets
        for value in (item.source_report_date or item.business_date,)
        if value
    })
    filename_mismatch = any(
        filename_date_mismatch(
            item.source_upload.original_filename,
            item.source_report_date or item.business_date,
        )
        for item in comparable_datasets
    )
    records: dict[str, list[dict[str, Any]]] = {}
    for dataset in datasets:
        records.setdefault(dataset.dataset_type, []).extend({"id": str(record.id), "record_type": record.record_type, **record.payload, "source": {**record.source_ref, "filename": dataset.source_upload.original_filename}} for record in dataset.records)
    if module == "accounting":
        if records.get("accounting_balance_sheet"):
            records["accounting_balance_sheet_summary"] = condensed_balance_sheet(records["accounting_balance_sheet"])
        records["readiness"] = [
            {"requirement": localize_text("Авторитетный бухгалтерский пакет", language), "status": "received" if datasets else "expected", "detail": localize_text("Текущие книги доступны только для landing/DQ; официальный набор ещё не подтверждён.", language)},
            {"requirement": localize_text("Период и единицы учёта", language), "status": "review" if datasets else "expected", "detail": localize_text("Проверяются конфликты дат, названий и валют.", language)},
            {"requirement": localize_text("Проверка формул и внешних ссылок", language), "status": "review" if datasets else "expected", "detail": localize_text("Ошибки формул сохраняются как доказательство и не публикуются как нули.", language)},
            {"requirement": localize_text("Независимое утверждение бухгалтерских метрик", language), "status": "expected", "detail": localize_text("Недоступно до получения полного источника и контракта показателей.", language)},
        ]
    summaries: dict[str, Any] = {item.dataset_type: item.summary for item in datasets}
    if module == "accounting":
        summaries["readiness"] = {"received_file_count": len(datasets), "official_metrics_available": False}
    if module == "brokerage":
        ledger = next((item for item in datasets if item.dataset_type == "brokerage_trade_ledger"), None)
        if ledger is not None and ledger.business_date is not None:
            # Charts that compare currencies (e.g. stocks vs bonds turnover)
            # need a KZT rate per currency, not a pre-aggregated total - the
            # frontend still has to apply the page's own repo/search filters
            # before summing, which this summary blob doesn't know about.
            # Reuses the same NBK-rate resolver as the Excel export so "KZT
            # equivalent" means the same thing in both places.
            currencies = sorted({str(record.payload.get("currency") or "").strip() for record in ledger.records if record.payload.get("currency")})
            fx_rates = {currency: str(rate.rate) for currency in currencies if (rate := resolve_export_fx_rate(currency, ledger.business_date)) is not None}
            summaries["brokerage_trade_ledger"] = {
                **(summaries.get("brokerage_trade_ledger") or {}),
                "fx_rates_kzt": fx_rates,
                "fx_rate_date": ledger.business_date.isoformat(),
            }
    return {
        "module": module,
        "available": bool(statement_datasets) if module == "accounting" else bool(datasets),
        "report_date_mismatch": len(dates) > 1,
        "filename_date_mismatch": filename_mismatch,
        "report_dates": dates,
        "sources": [dataset_manifest(item) for item in datasets],
        "summaries": summaries,
        "records": records,
        "disclosure": localize_text("Операционные/данные из источника; не утверждённый бухгалтерский NAV или показатель доходности.", language),
        "pinned_dataset_types": pinned_dataset_types,
        "selected_source_upload_id": str(source_upload_id) if source_upload_id is not None else None,
        "missing_source_dataset_types": missing_source_dataset_types,
        **({
            "history": risk_trend_history(session, uploader_id=uploader_id),
            "risk_utilization_history": risk_utilization_history(session, uploader_id=uploader_id),
        } if module == "risk" else {}),
        **({"account_mapping": {
            dataset_type: account_code_registry(session, dataset_type, uploader_id=uploader_id)
            for dataset_type in _ACCOUNT_CODE_DATASET_TYPES
        }} if module == "accounting" else {}),
    }


def dataset_manifest(dataset: DatasetVersion) -> dict[str, Any]:
    return {
        "dataset_id": str(dataset.id), "source_upload_id": str(dataset.source_upload_id), "dataset_type": dataset.dataset_type,
        "scope_type": dataset.scope_type, "scope_code": dataset.scope_code,
        "source_filename": dataset.source_upload.original_filename,
        "source_report_date": dataset.source_report_date.isoformat() if dataset.source_report_date else None,
        "business_date": dataset.business_date.isoformat() if dataset.business_date else None,
        "version": dataset.version, "status": dataset.status.value,
        "generated_at": dataset.generated_at.isoformat() if dataset.generated_at else None,
        "parser_version": dataset.parser_version,
        "freshness": _freshness(dataset.business_date),
        "dq_blocker_count": sum(issue.severity == "blocker" for issue in dataset.issues),
        "dq_high_count": sum(issue.severity == "high" for issue in dataset.issues),
    }


def _freshness(business_date: date | None) -> str:
    if business_date is None:
        return "unavailable"
    today = date.today()  # see _readiness_status's comment: not utcnow().date()
    age = (today - business_date).days
    if age < 0:
        # Some report dates are the last day of a stated reporting period
        # (see _russian_period_end in ingestion/multi_source.py, used for the
        # derivatives register's "Лист7" header) rather than a literal as-of
        # timestamp - a report titled "July 2026" legitimately carries a
        # 31 July date before the month is over. That's a normal monthly-
        # period labeling convention, not a wrong/injected future date, so
        # only flag a business date that falls outside the current calendar
        # month as genuinely suspicious.
        if business_date.year == today.year and business_date.month == today.month:
            return "fresh"
        return "future"
    if age <= 1:
        return "fresh"
    if age <= 7:
        return "aging"
    return "stale"


def reconcile_fund(session: Session, scope_code: str) -> None:
    valuation = latest_published(session, "fund_valuation", scope_code)
    units = latest_published(session, "fund_unit_series", scope_code)
    osip = session.scalar(select(PortfolioSnapshotRecord).join(ImportBatch).where(
        PortfolioSnapshotRecord.portfolio_code == scope_code,
        ImportBatch.status == ImportStatus.PUBLISHED,
    ).order_by(PortfolioSnapshotRecord.report_date.desc()))
    if valuation and osip:
        _reconciliation(session, "FUND-SECURITIES", scope_code, valuation.business_date, [str(valuation.id), str(osip.import_id)],
            {"valuation": valuation.summary.get("securities_value_kzt"), "osip": str(osip.derived_carrying_value_kzt)}, Decimal("1"), valuation.source_report_date == osip.report_date)
        _reconciliation(session, "FUND-CASH", scope_code, valuation.business_date, [str(valuation.id), str(osip.import_id)],
            {"valuation": valuation.summary.get("cash_kzt"), "osip": str(osip.cash_kzt)}, Decimal("1"), valuation.source_report_date == osip.report_date)
    if valuation and units:
        observations = [record for record in units.records if record.record_type == "unit_observation"]
        latest = max(observations, key=lambda item: item.payload.get("date") or "", default=None)
        if latest:
            _reconciliation(session, "FUND-NAV-UNIT-SERIES", scope_code, valuation.business_date, [str(valuation.id), str(units.id)],
                {"valuation": valuation.summary.get("nav_kzt"), "unit_series": latest.payload.get("nav_kzt")}, Decimal("1"), valuation.business_date == units.business_date)


def reconcile_accounting_portfolio(session: Session, dataset: DatasetVersion) -> None:
    """Compare the accounting portfolio workbook's total against OSIP carrying value.

    The workbook's own scope is the fixed business_domain "ACCOUNTING" - it
    does not say which OSIP portfolio it represents, so the uploader must
    supply that explicitly (reconciliation_portfolio_code, set at
    materialize time; see materialize_datasets). Nothing is inferred from
    the sheet name or filename. If it wasn't supplied, this is a no-op:
    an unconfirmed portfolio match is not reconciled rather than guessed.
    Uses the same carrying-value basis and Decimal("1") KZT tolerance as
    the existing FUND-SECURITIES reconciliation, for one consistent
    reconciliation policy rather than a second bespoke one.
    """
    portfolio_code = str((dataset.summary or {}).get("reconciliation_portfolio_code") or "").strip().upper()
    if not portfolio_code:
        return
    osip = session.scalar(select(PortfolioSnapshotRecord).join(ImportBatch).where(
        PortfolioSnapshotRecord.portfolio_code == portfolio_code,
        ImportBatch.status == ImportStatus.PUBLISHED,
    ).order_by(PortfolioSnapshotRecord.report_date.desc()))
    if osip is None:
        return
    _reconciliation(
        session, "ACCOUNTING-PORTFOLIO", portfolio_code, dataset.business_date,
        [str(dataset.id), str(osip.import_id)],
        {"accounting": dataset.summary.get("total_carrying_value_kzt"), "osip": str(osip.derived_carrying_value_kzt)},
        Decimal("1"), dataset.business_date == osip.report_date,
    )


def _reconciliation(session: Session, code: str, scope: str, business_date: date | None, ids: list[str], values: dict[str, Any], tolerance: Decimal, dates_match: bool) -> None:
    numeric = [Decimal(str(value)) for value in values.values() if value is not None]
    difference = abs(numeric[0] - numeric[1]) if len(numeric) == 2 else None
    status = "date_mismatch" if not dates_match else "pass" if difference is not None and difference <= tolerance else "fail"
    # Keyed on (rule, scope, date) alone, not also on dataset_ids - a later
    # evaluation always supersedes an earlier one for the same check, even
    # when the underlying dataset was republished with new IDs (a routine
    # same-day re-upload/reparse). Matching on dataset_ids too left the old
    # row behind forever in that case, silently doubling the reconciliation
    # table and inflating the Operations page's mismatch count.
    candidates = list(session.scalars(select(ReconciliationResult).where(
        ReconciliationResult.rule_code == code,
        ReconciliationResult.scope_code == scope,
        ReconciliationResult.business_date == business_date,
    )))
    if candidates:
        result = candidates[0]
        for duplicate in candidates[1:]:
            session.delete(duplicate)
        result.dataset_ids = ids
        result.actual_values = values
        result.difference = difference
        result.tolerance = tolerance
        result.status = status
        result.evidence = {"dates_match": dates_match}
        return
    session.add(ReconciliationResult(rule_code=code, scope_code=scope, business_date=business_date, dataset_ids=ids, actual_values=values, difference=difference, tolerance=tolerance, status=status, evidence={"dates_match": dates_match}))


def _persist_parsed(session: Session, dataset: DatasetVersion, parsed: ParsedDataset) -> None:
    # A workbook can legitimately contain repeated source keys (for example,
    # several price rows for the same ticker). Preserve every row and its
    # source reference while making the database key deterministic and unique
    # within this dataset. The payload and raw evidence are never changed.
    seen: set[tuple[str, str]] = set()
    for item in parsed.records:
        record_type = str(item["record_type"])
        original_key = str(item["record_key"])
        record_key = original_key
        identity = (record_type, record_key)
        source_row = item.get("source_ref", {}).get("row_number")
        if identity in seen:
            suffix = f":row-{source_row}" if source_row is not None else ":duplicate"
            record_key = f"{original_key}{suffix}"
            counter = 2
            while (record_type, record_key) in seen:
                record_key = f"{original_key}{suffix}-{counter}"
                counter += 1
            identity = (record_type, record_key)
        seen.add(identity)
        session.add(DatasetRecord(dataset=dataset, **{**item, "record_key": record_key}))
    for issue in parsed.issues:
        session.add(DatasetIssue(dataset=dataset, code=issue.code, severity=issue.severity, message=issue.message, affected_fields=list(issue.affected_fields), source_refs=list(issue.source_refs)))


def _audit(session: Session, dataset: DatasetVersion, actor_id: str, action: str, detail: dict[str, Any] | None = None) -> None:
    session.add(DatasetAuditEvent(dataset=dataset, actor_id=actor_id, action=action, detail=detail or {}))
