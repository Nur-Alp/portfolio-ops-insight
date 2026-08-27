"""Import-workflow (upload/review/publish) HTTP handlers."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal
import re
from typing import Any
from uuid import UUID

from fastapi import File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from python_calamine import CalamineWorkbook
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from osip_dashboard.api_schemas import ApprovalRequest, RejectionRequest, WithdrawalRequest
from osip_dashboard.identity import require_domain, require_portfolio, require_role
from osip_dashboard.persistence.models import (
    AuditEvent,
    DatasetRecord,
    ImportBatch,
    ImportStatus,
    SourceRow,
)
from osip_dashboard.services.holdings_export import create_import_registry_xlsx
from osip_dashboard.services.instrument_dictionary import (
    DictionaryValidationError,
    dictionary_source_path,
    instrument_class,
    instrument_dictionary,
    replace_instrument_dictionary,
    true_asset_class,
)
from osip_dashboard.services.imports import UploadValidationError, import_workbook, normalize_portfolio_code
from osip_dashboard.services.multi_source import reconcile_fund
from osip_dashboard.services.comparison import compare_import_to_prior_approved
from osip_dashboard.services.dividends import (
    DividendValidationError,
    dividend_data_status,
    replace_dividend_history,
)
from osip_dashboard.services.workflow import (
    Actor,
    WorkflowError,
    approve_import,
    get_import_or_error,
    publish_import,
    publish_import_source_first,
    reject_import,
    withdraw_import,
)

from .shared import ActorDep, SessionDep, XlsxResponse, _dividend_status_payload, _excel_column_letter, _iso, _decimal, router


@router.post("/imports", status_code=201)
async def create_import(
    response: Response,
    session: SessionDep,
    actor: ActorDep,
    request: Request,
    file: UploadFile = File(...),
    portfolio_code: str = Form(...),
    portfolio_name: str | None = Form(None),
) -> dict[str, Any]:
    require_role(actor, "uploader")
    require_domain(actor, "back_office")
    try:
        normalized_portfolio_code = normalize_portfolio_code(portfolio_code)
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    require_portfolio(actor, normalized_portfolio_code)
    limit = request.app.state.settings.max_upload_bytes
    content = await file.read(limit + 1)
    try:
        outcome = import_workbook(
            session,
            request.app.state.blob_store,
            filename=file.filename or "",
            content=content,
            portfolio_code=normalized_portfolio_code,
            portfolio_name=portfolio_name,
            uploader_id=actor.actor_id,
            max_upload_bytes=limit,
        )
        # Local domain-owner mode treats a structurally valid OSIP workbook as
        # the authoritative input. Semantic DQ findings remain visible source
        # evidence, but do not require a second person or acknowledgement.
        # Controlled/hosted deployments keep the explicit review workflow.
        if (
            request.app.state.settings.source_first_mode
            and outcome.import_batch.status == ImportStatus.VALIDATED
        ):
            publish_import_source_first(
                session,
                outcome.import_batch.id,
                actor_id="source-system",
            )
            if normalized_portfolio_code in {"TABYS", "SAQ"}:
                reconcile_fund(session, normalized_portfolio_code)
        # A duplicate hash returns its original immutable import. Check that
        # object too, not only the portfolio code submitted with this request.
        require_portfolio(actor, outcome.import_batch.portfolio_code)
        session.commit()
    except UploadValidationError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if outcome.duplicate:
        response.status_code = 200
    return _import_payload(outcome.import_batch, duplicate=outcome.duplicate)


@router.get("/reference-data/classes-and-ratings")
def get_reference_dictionary_status(actor: ActorDep) -> dict[str, Any]:
    require_role(actor, "reader")
    row_count = len(instrument_dictionary())
    path = dictionary_source_path()
    updated_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else None
    return {"row_count": row_count, "updated_at": updated_at}


@router.post("/reference-data/classes-and-ratings")
async def upload_reference_dictionary(
    actor: ActorDep,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    # Gated the same as an OSIP workbook upload: this is a controlled
    # reference artifact (it silently reclassifies every portfolio's rating
    # buckets the moment it lands), not free-form data entry.
    require_role(actor, "uploader")
    content = await file.read()
    try:
        result = replace_instrument_dictionary(filename=file.filename or "", content=content)
    except DictionaryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "row_count": result.row_count,
        "previous_row_count": result.previous_row_count,
        "added_isins": result.added_isins,
        "removed_isins": result.removed_isins,
        "changed_isins": result.changed_isins,
    }


@router.get("/reference-data/dividends")
def get_dividend_data_status(actor: ActorDep) -> dict[str, Any]:
    require_role(actor, "reader")
    return _dividend_status_payload(dividend_data_status())


@router.post("/reference-data/dividends")
async def upload_dividend_data(
    actor: ActorDep,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    require_role(actor, "uploader")
    content = await file.read()
    try:
        status = replace_dividend_history(filename=file.filename or "", content=content)
    except DividendValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _dividend_status_payload(status)


@router.get("/imports")
def list_imports(
    session: SessionDep,
    actor: ActorDep,
    portfolio: str | None = None,
    report_date: date | None = None,
    status: ImportStatus | None = None,
    include_withdrawn: bool = Query(False),
) -> dict[str, Any]:
    require_role(actor, "reader")
    require_domain(actor, "back_office")
    statement = select(ImportBatch).order_by(ImportBatch.created_at.desc())
    if portfolio:
        require_portfolio(actor, portfolio)
        statement = statement.where(ImportBatch.portfolio_code == portfolio.upper())
    elif "*" not in actor.portfolios:
        statement = statement.where(
            or_(
                ImportBatch.portfolio_code.in_(actor.portfolios),
                (ImportBatch.portfolio_code.is_(None))
                & (ImportBatch.uploader_id == actor.actor_id),
            )
        )
    if report_date:
        statement = statement.where(ImportBatch.report_date == report_date)
    if status:
        statement = statement.where(ImportBatch.status == status)
    elif not include_withdrawn:
        statement = statement.where(ImportBatch.status != ImportStatus.WITHDRAWN)
    batches = list(session.scalars(statement))
    return {"items": [_import_payload(batch) for batch in batches]}


@router.get("/imports/export")
def export_import_registry(
    session: SessionDep, actor: ActorDep
) -> XlsxResponse:
    """Download the reader-visible immutable import registry and its audit."""
    require_role(actor, "reader")
    require_domain(actor, "back_office")
    statement = select(ImportBatch).where(
        ImportBatch.status != ImportStatus.WITHDRAWN
    ).order_by(ImportBatch.created_at.desc())
    if "*" not in actor.portfolios:
        statement = statement.where(
            or_(
                ImportBatch.portfolio_code.in_(actor.portfolios),
                (ImportBatch.portfolio_code.is_(None))
                & (ImportBatch.uploader_id == actor.actor_id),
            )
        )
    batches = list(session.scalars(statement))
    content = create_import_registry_xlsx(batches)
    filename = "OSIP_import_registry.xlsx"
    session.add(
        AuditEvent(
            actor_id=actor.actor_id,
            action="imports_registry.exported",
            detail={"format": "xlsx", "row_count": len(batches), "filename": filename},
        )
    )
    session.commit()
    return XlsxResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/imports/{import_id}")
def get_import(
    import_id: UUID, session: SessionDep, actor: ActorDep
) -> dict[str, Any]:
    require_role(actor, "reader")
    return _import_payload(_get_import(session, import_id, actor), include_audit=True)


@router.get("/imports/{import_id}/comparison")
def get_import_comparison(
    import_id: UUID, session: SessionDep, actor: ActorDep
) -> dict[str, Any]:
    require_role(actor, "reader")
    batch = _get_import(session, import_id, actor)
    try:
        comparison = compare_import_to_prior_approved(session, batch)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "current": _comparison_import(comparison["current"]),
        "baseline": _comparison_import(comparison["baseline"])
        if comparison["baseline"]
        else None,
        "metrics": {
            name: {
                "current": _comparison_value(values["current"]),
                "baseline": _comparison_value(values["baseline"]),
                "delta": _comparison_value(values["delta"]),
                "basis": values["basis"],
            }
            for name, values in comparison["metrics"].items()
        },
        "lot_changes": comparison["lot_changes"],
    }


@router.get("/imports/{import_id}/source")
def get_import_source(
    import_id: UUID, session: SessionDep, actor: ActorDep, request: Request
) -> FileResponse:
    require_role(actor, "reader")
    batch = _get_import(session, import_id, actor)
    source_path = request.app.state.blob_store.path_for(batch.storage_key)
    if not source_path.exists():
        raise HTTPException(status_code=500, detail="Сохранённый файл источника недоступен")
    return FileResponse(
        source_path,
        filename=batch.original_filename,
        media_type="application/vnd.ms-excel",
    )


@router.get("/source-rows/{source_row_id}/preview")
def source_row_preview(
    source_row_id: UUID,
    session: SessionDep,
    actor: ActorDep,
    request: Request,
    cell: str = Query(..., min_length=2, max_length=32),
) -> dict[str, Any]:
    """Return a small, read-only view centered on an immutable source cell.

    ``source_row_id`` identifies either an OSIP ``SourceRow`` (persisted
    immutable evidence) or, for multi-source domains such as Risk, a
    ``DatasetRecord`` - those never persist a row-level table, so this path
    re-opens the original workbook from blob storage instead.
    """
    require_role(actor, "reader")
    match = re.fullmatch(r"([A-Za-z]{1,3})(\d+)", cell.strip())
    if match is None:
        raise HTTPException(status_code=422, detail="Адрес ячейки должен иметь формат A1")
    column = _excel_column_number(match.group(1))
    requested_row = int(match.group(2))
    source_row = session.get(SourceRow, source_row_id)
    if source_row is None:
        dataset_record = session.get(DatasetRecord, source_row_id)
        if dataset_record is None:
            raise HTTPException(status_code=404, detail="Строка исходной рабочей книги не найдена")
        return _dataset_record_preview(dataset_record, column, requested_row, request, actor)
    batch = _get_import(session, source_row.import_id, actor)
    if requested_row != source_row.row_number:
        raise HTTPException(status_code=409, detail="Адрес ячейки не соответствует исходной строке")
    context_rows = list(session.scalars(
        select(SourceRow)
        .where(
            SourceRow.import_id == source_row.import_id,
            SourceRow.sheet_name == source_row.sheet_name,
            SourceRow.row_number.between(max(1, source_row.row_number - 4), source_row.row_number + 4),
        )
        .order_by(SourceRow.row_number)
    ))
    # Every sheet in this app has its column headers within the first ~10
    # rows (confirmed across all risk/OSIP sheets). Always including that
    # header band - not just the window centered on the target row - means
    # the preview is never just bare column letters. This must run even when
    # the target row itself is <= 10: a target a few rows below the header
    # (e.g. row 9, window rows 5-13) can still miss the actual header rows
    # (1-4) if the two ranges don't happen to overlap.
    #
    # The header band is read directly from the original workbook rather
    # than from persisted SourceRow entities: ingestion only persists the
    # rows it actually parsed as data, which can skip the real header rows
    # entirely (e.g. a reference/lookup block above the parsed table) -
    # querying SourceRow for "row_number <= 10" would then silently return
    # whatever data rows happen to survive that filter, and the "most
    # text-dense row" heuristic below would confidently mislabel one of
    # them as the header instead.
    header_rows: list[dict[str, Any]] = []
    try:
        blob_store = request.app.state.blob_store
        workbook = CalamineWorkbook.from_path(blob_store.path_for(batch.storage_key))
        if source_row.sheet_name in workbook.sheet_names:
            sheet_rows = workbook.get_sheet_by_name(source_row.sheet_name).to_python(skip_empty_area=False)
            header_rows = [
                {"row_number": offset + 1, "values": [_preview_value(value) for value in sheet_row]}
                for offset, sheet_row in enumerate(sheet_rows[:min(10, len(sheet_rows))])
            ]
    except (OSError, ValueError, KeyError):
        header_rows = []
    if not header_rows:
        header_rows = [
            {"row_number": row.row_number, "values": [_preview_value(value) for value in row.raw_values]}
            for row in session.scalars(
                select(SourceRow)
                .where(
                    SourceRow.import_id == source_row.import_id,
                    SourceRow.sheet_name == source_row.sheet_name,
                    SourceRow.row_number <= 10,
                )
                .order_by(SourceRow.row_number)
            )
        ]
    rows = _merge_preview_rows(
        header_rows,
        [{"row_number": row.row_number, "values": [_preview_value(value) for value in row.raw_values]} for row in context_rows],
    )
    max_columns = max([column, *(len(row["values"]) for row in rows)], default=column)
    target_values = next((row["values"] for row in rows if row["row_number"] == source_row.row_number), [])
    header_row = _infer_header_row(header_rows)
    return {
        "workbook_name": source_row.workbook_name,
        "sheet_name": source_row.sheet_name,
        "target_cell": f"{_excel_column_letter(column)}{source_row.row_number}",
        "target_row": source_row.row_number,
        "target_column": column,
        "target_value": target_values[column - 1] if len(target_values) >= column else None,
        "columns": [_excel_column_letter(index) for index in range(1, max_columns + 1)],
        "rows": rows,
        "header_row": header_row["row_number"] if header_row else None,
        "column_labels": header_row["values"] if header_row else [],
        "import_id": str(batch.id),
        "original_filename": batch.original_filename,
    }


def _dataset_record_preview(record: DatasetRecord, column: int, requested_row: int, request: Request, actor: Actor) -> dict[str, Any]:
    # Imported locally: routes.multi_source doesn't import this module, so
    # this doesn't introduce a cycle, but importing at call time (rather than
    # module load time) keeps that true even if that ever changes.
    from osip_dashboard.routes.multi_source import _require_dataset_access

    dataset = record.dataset
    _require_dataset_access(actor, dataset)
    source_ref = record.source_ref or {}
    sheet_name = str(source_ref.get("sheet_name") or "")
    row_number = source_ref.get("row_number")
    if not sheet_name or row_number is None or int(row_number) != requested_row:
        raise HTTPException(status_code=409, detail="Адрес ячейки не соответствует исходной строке")
    upload = dataset.source_upload
    blob_store = request.app.state.blob_store
    workbook = CalamineWorkbook.from_path(blob_store.path_for(upload.storage_key))
    if sheet_name not in workbook.sheet_names:
        raise HTTPException(status_code=404, detail="Лист рабочей книги недоступен")
    sheet_rows = workbook.get_sheet_by_name(sheet_name).to_python(skip_empty_area=False)
    start = max(0, requested_row - 5)
    end = min(len(sheet_rows), requested_row + 4)
    window_rows = [
        {"row_number": start + offset + 1, "values": [_preview_value(value) for value in sheet_row]}
        for offset, sheet_row in enumerate(sheet_rows[start:end])
    ]
    # See the matching comment in source_row_preview: always include the
    # sheet's header band, not just the window around the target row - a
    # target row <= 10 whose window doesn't happen to reach row 1 (e.g. row
    # 9's window is rows 5-13) would otherwise still miss the real header.
    header_rows = [
        {"row_number": offset + 1, "values": [_preview_value(value) for value in sheet_row]}
        for offset, sheet_row in enumerate(sheet_rows[:min(10, len(sheet_rows))])
    ]
    rows = _merge_preview_rows(header_rows, window_rows)
    max_columns = max([column, *(len(row["values"]) for row in rows)], default=column)
    target_values = next((row["values"] for row in rows if row["row_number"] == requested_row), [])
    header_row = _infer_header_row(header_rows)
    return {
        "workbook_name": upload.original_filename,
        "sheet_name": sheet_name,
        "target_cell": f"{_excel_column_letter(column)}{requested_row}",
        "target_row": requested_row,
        "target_column": column,
        "target_value": target_values[column - 1] if len(target_values) >= column else None,
        "columns": [_excel_column_letter(index) for index in range(1, max_columns + 1)],
        "rows": rows,
        "header_row": header_row["row_number"] if header_row else None,
        "column_labels": header_row["values"] if header_row else [],
        "import_id": str(dataset.id),
        "original_filename": upload.original_filename,
        "source_upload_id": str(upload.id),
    }


@router.post("/imports/{import_id}/approve")
def approve(
    import_id: UUID,
    body: ApprovalRequest,
    session: SessionDep,
    actor: ActorDep,
) -> dict[str, Any]:
    require_role(actor, "reviewer")
    _get_import(session, import_id, actor)
    try:
        batch = approve_import(
            session,
            import_id,
            actor=actor,
            comment=body.comment,
            acknowledged_codes=body.acknowledged_dq_codes,
        )
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _import_payload(batch, include_audit=True)


@router.post("/imports/{import_id}/reject")
def reject(
    import_id: UUID,
    body: RejectionRequest,
    session: SessionDep,
    actor: ActorDep,
) -> dict[str, Any]:
    require_role(actor, "reviewer")
    _get_import(session, import_id, actor)
    try:
        batch = reject_import(session, import_id, actor=actor, reason=body.reason)
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _import_payload(batch, include_audit=True)


@router.post("/imports/{import_id}/withdraw")
def withdraw(
    import_id: UUID,
    body: WithdrawalRequest,
    session: SessionDep,
    actor: ActorDep,
) -> dict[str, Any]:
    require_role(actor, "publisher")
    _get_import(session, import_id, actor)
    try:
        batch = withdraw_import(session, import_id, actor=actor, reason=body.reason)
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _import_payload(batch, include_audit=True)


@router.post("/imports/{import_id}/publish")
def publish(
    import_id: UUID, session: SessionDep, actor: ActorDep
) -> dict[str, Any]:
    require_role(actor, "publisher")
    _get_import(session, import_id, actor)
    try:
        batch = publish_import(session, import_id, actor=actor)
        if batch.portfolio_code in {"TABYS", "SAQ"}:
            reconcile_fund(session, batch.portfolio_code)
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _import_payload(batch, include_audit=True)


def _get_import(session: Session, import_id: UUID, actor: Actor) -> ImportBatch:
    try:
        batch = get_import_or_error(session, import_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if batch.portfolio_code is None and batch.uploader_id != actor.actor_id and "*" not in actor.portfolios:
        raise HTTPException(status_code=403, detail="Нет доступа к загрузке")
    require_domain(actor, "back_office")
    require_portfolio(actor, batch.portfolio_code)
    return batch


def _import_payload(
    batch: ImportBatch, *, duplicate: bool = False, include_audit: bool = False
) -> dict[str, Any]:
    snapshot = batch.snapshot
    counts = Counter(issue.severity for issue in snapshot.issues) if snapshot else Counter()
    payload: dict[str, Any] = {
        "id": str(batch.id),
        "portfolio": batch.portfolio_code,
        "report_date": _iso(batch.report_date),
        "version": batch.version,
        "status": batch.status.value,
        "duplicate": duplicate,
        "source_sha256": batch.source_sha256,
        "original_filename": batch.original_filename,
        "parser_version": batch.parser_version,
        "uploader_id": batch.uploader_id,
        "reviewer_id": batch.reviewer_id,
        "publisher_id": batch.publisher_id,
        "review_comment": batch.review_comment,
        "rejection_reason": batch.rejection_reason,
        "error_message": batch.error_message,
        "created_at": _iso(batch.created_at),
        "validated_at": _iso(batch.validated_at),
        "approved_at": _iso(batch.approved_at),
        "published_at": _iso(batch.published_at),
        "snapshot_id": str(snapshot.id) if snapshot else None,
        "summary": {
            "position_count": snapshot.position_count,
            "unique_isin_count": snapshot.unique_isin_count,
            "raw_settlement_count": snapshot.raw_settlement_count,
            "settlement_count": snapshot.settlement_count,
            "purchase_amount_kzt": _decimal(snapshot.purchase_amount_kzt),
            "derived_carrying_value_kzt": _decimal(
                snapshot.derived_carrying_value_kzt
            ),
            "cash_kzt": _decimal(snapshot.cash_kzt),
            "derived_operational_total_kzt": _decimal(
                snapshot.derived_operational_total_kzt
            ),
        }
        if snapshot
        else None,
        "dq_counts": {
            severity: counts.get(severity, 0)
            for severity in ("blocker", "high", "medium", "low")
        },
        "publication_basis": (
            "trusted_source_local"
            if batch.publisher_id == "source-system"
            else "controlled_workflow"
        ),
        "publication_requires_override": bool(
            batch.publisher_id != "source-system"
            and (counts.get("blocker", 0) or counts.get("high", 0))
        ),
    }
    if include_audit:
        payload["audit_events"] = [
            {
                "id": str(event.id),
                "actor_id": event.actor_id,
                "action": event.action,
                "detail": event.detail,
                "created_at": _iso(event.created_at),
            }
            for event in sorted(batch.audit_events, key=lambda event: event.created_at)
        ]
    return payload


def _comparison_import(batch: ImportBatch) -> dict[str, Any]:
    return {
        "import_id": str(batch.id),
        "snapshot_id": str(batch.snapshot.id),
        "portfolio": batch.portfolio_code,
        "report_date": _iso(batch.report_date),
        "version": batch.version,
        "status": batch.status.value,
        "source_sha256": batch.source_sha256,
    }


def _comparison_value(value: Any) -> str | int | None:
    if isinstance(value, Decimal):
        return _decimal(value)
    return value


def _excel_column_number(letters: str) -> int:
    value = 0
    for letter in letters.upper():
        value = value * 26 + ord(letter) - ord("A") + 1
    return value


def _preview_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _merge_preview_rows(header_rows: list[dict[str, Any]], window_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine the sheet's header band with the rows centered on the target,
    de-duplicating where they overlap (a target near the top of the sheet)
    and keeping everything in row order."""
    by_row_number = {row["row_number"]: row for row in header_rows}
    by_row_number.update({row["row_number"]: row for row in window_rows})
    return [by_row_number[key] for key in sorted(by_row_number)]


def _infer_header_row(header_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the row within the header band that most looks like the actual
    column-title row, so the preview can label columns by their real header
    text instead of a bare Excel letter (which tells a reader nothing about
    what a "BBB" or "Baa2" cell value actually means).

    Report titles and merged-cell captions tend to sit in the earliest rows
    of the band with few populated cells, so the row with the most text-like
    cells is preferred over them. Ties are broken toward the earlier row
    number, since a header always precedes the data it labels - the reverse
    would risk picking a same-density data row instead (observed with rating
    columns, where each row is just as text-dense as any header would be).
    """
    def score(row: dict[str, Any]) -> tuple[int, int]:
        text_cells = sum(1 for value in row["values"] if isinstance(value, str) and value.strip())
        return (text_cells, -row["row_number"])

    candidates = [row for row in header_rows if any(isinstance(value, str) and value.strip() for value in row["values"])]
    if not candidates:
        return None
    return max(candidates, key=score)
