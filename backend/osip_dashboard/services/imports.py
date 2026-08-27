"""OSIP source-file validation and canonical snapshot persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from osip_dashboard.domain import PortfolioSnapshot, SettlementEvent
from osip_dashboard.ingestion.osip_workbook import OsipWorkbookError, parse_osip_workbook
from osip_dashboard.persistence.models import (
    AuditEvent,
    CashBalanceRecord,
    DataQualityIssueRecord,
    ImportBatch,
    ImportStatus,
    InstrumentRecord,
    MetricDefinition,
    Portfolio,
    PortfolioSnapshotRecord,
    PositionLotRecord,
    SettlementEventRecord,
    SettlementSourceLink,
    SourceRow,
    SourceUpload,
    utcnow,
)
from osip_dashboard.storage import BlobStore


OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
PARSER_VERSION = "osip-calamine-v1"
MONEY_QUANTUM = Decimal("0.000000000001")
ZERO = Decimal("0")
PORTFOLIO_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,15}$")
PORTFOLIO_SEEDS = (
    ("SOBSTV", "Собственные средства", "KZT"),
    ("TABYS", "TABYS", "KZT"),
)
METRIC_SEEDS = (
    ("position_count", "Current lots", "source", "count", None, True, None),
    ("unique_isin_count", "Unique instruments", "source", "count", None, True, None),
    ("purchase_amount_kzt", "Purchase amount", "source", "KZT", None, True, None),
    (
        "derived_carrying_value_kzt",
        "Derived carrying value",
        "derived",
        "KZT",
        "AA × AU × AT + AR",
        True,
        None,
    ),
    ("cash_kzt", "Cash equivalent", "source", "KZT", None, True, None),
    (
        "derived_operational_total_kzt",
        "Derived operational total",
        "derived",
        "KZT",
        "derived_carrying_value_kzt + cash_kzt",
        True,
        None,
    ),
    ("total_fees_kzt", "Organizer and broker fees", "source", "KZT", None, True, None),
    ("total_reserves_kzt", "Reported reserves", "source", "KZT", None, True, None),
    (
        "official_nav_kzt",
        "Official NAV",
        "unavailable",
        "KZT",
        None,
        False,
        "Approved prices, liabilities, cash flows, valuation policy, and NAV approval are unavailable.",
    ),
    (
        "official_performance",
        "Official performance",
        "unavailable",
        "percent",
        None,
        False,
        "Historical NAV, external cash flows, benchmark data, and approved methodology are unavailable.",
    ),
)


class UploadValidationError(ValueError):
    """The upload cannot be accepted as an OSIP source file."""


@dataclass(frozen=True)
class ImportOutcome:
    import_batch: ImportBatch
    duplicate: bool = False


def ensure_seed_portfolios(session: Session) -> None:
    for code, name, currency in PORTFOLIO_SEEDS:
        if session.get(Portfolio, code) is None:
            session.add(
                Portfolio(code=code, name=name, reporting_currency=currency)
            )
    session.flush()


def ensure_reference_data(session: Session) -> None:
    ensure_seed_portfolios(session)
    for code, label, basis, unit, formula, enabled, unavailable_reason in METRIC_SEEDS:
        if session.get(MetricDefinition, code) is None:
            session.add(
                MetricDefinition(
                    code=code,
                    label=label,
                    basis=basis,
                    unit=unit,
                    formula=formula,
                    version="1.0",
                    enabled=enabled,
                    unavailable_reason=unavailable_reason,
                )
            )
    session.flush()


def normalize_portfolio_code(value: str) -> str:
    code = value.strip().upper()
    if not PORTFOLIO_CODE_PATTERN.fullmatch(code):
        raise UploadValidationError(
            "Код портфеля должен содержать 2–16 латинских букв, цифр, дефисов или подчёркиваний"
        )
    return code


def ensure_portfolio(
    session: Session, *, portfolio_code: str, portfolio_name: str | None
) -> Portfolio:
    existing = session.get(Portfolio, portfolio_code)
    if existing is not None:
        return existing
    name = (portfolio_name or "").strip() or portfolio_code
    if len(name) > 120:
        raise UploadValidationError("Наименование портфеля не должно превышать 120 символов")
    portfolio = Portfolio(
        code=portfolio_code,
        name=name,
        reporting_currency="KZT",
    )
    session.add(portfolio)
    session.flush()
    return portfolio


def import_workbook(
    session: Session,
    blob_store: BlobStore,
    *,
    filename: str,
    content: bytes,
    portfolio_code: str,
    portfolio_name: str | None = None,
    uploader_id: str,
    max_upload_bytes: int,
) -> ImportOutcome:
    """Validate, store, parse, and persist one immutable workbook version."""
    safe_filename = Path(filename.replace("\\", "/")).name
    _validate_upload(safe_filename, content, max_upload_bytes)
    normalized_portfolio_code = normalize_portfolio_code(portfolio_code)
    source_sha256 = hashlib.sha256(content).hexdigest()
    existing_assignments = list(
        session.scalars(
            select(ImportBatch).where(ImportBatch.source_sha256 == source_sha256)
        )
    )
    # Rejected and failed imports never reached publication, so a retry of the
    # identical bytes should re-parse rather than being permanently stuck: only
    # withdraw is reserved for pulling something back from an active state.
    non_blocking_statuses = {ImportStatus.WITHDRAWN, ImportStatus.REJECTED, ImportStatus.FAILED}
    same_portfolio = next(
        (
            batch
            for batch in existing_assignments
            if batch.portfolio_code == normalized_portfolio_code
            and batch.status not in non_blocking_statuses
        ),
        None,
    )
    if same_portfolio is not None:
        return ImportOutcome(same_portfolio, duplicate=True)
    active_assignment = next(
        (
            batch
            for batch in existing_assignments
            if batch.status not in non_blocking_statuses
        ),
        None,
    )
    if active_assignment is not None:
        raise UploadValidationError(
            "Эта рабочая книга уже назначена портфелю "
            f"{active_assignment.portfolio_code}. Сначала снимите ошибочную версию с публикации."
        )

    ensure_reference_data(session)
    ensure_portfolio(
        session,
        portfolio_code=normalized_portfolio_code,
        portfolio_name=portfolio_name,
    )
    storage_key = blob_store.put(source_sha256, content)
    source_upload = session.scalar(
        select(SourceUpload).where(SourceUpload.source_sha256 == source_sha256)
    )
    if source_upload is None:
        source_upload = SourceUpload(
            source_sha256=source_sha256,
            original_filename=safe_filename,
            storage_key=storage_key,
            file_format="xls",
            detected_source_type="osip_portfolio",
            detection={
                "source_type": "osip_portfolio",
                "datasets": [{"key": "portfolio", "dataset_type": "portfolio_snapshot"}],
            },
            uploader_id=uploader_id,
        )
        session.add(source_upload)
        session.flush()
    batch = ImportBatch(
        source_upload_id=source_upload.id,
        dataset_type="portfolio_snapshot",
        scope_type="portfolio",
        scope_code=normalized_portfolio_code,
        portfolio_code=normalized_portfolio_code,
        source_sha256=source_sha256,
        original_filename=safe_filename,
        storage_key=storage_key,
        parser_version=PARSER_VERSION,
        status=ImportStatus.DRAFT,
        uploader_id=uploader_id,
    )
    session.add(batch)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        # The partial unique index only guards active-status rows, so a stale
        # withdrawn/rejected/failed row for the same (sha256, portfolio) can
        # coexist with the concurrent winner that triggered this conflict.
        # Excluding non-blocking statuses here (matching the pre-insert check
        # above) avoids nondeterministically picking the dead row instead of
        # the actual active duplicate.
        existing = session.scalar(
            select(ImportBatch).where(
                ImportBatch.source_sha256 == source_sha256,
                ImportBatch.portfolio_code == normalized_portfolio_code,
                ImportBatch.status.not_in(non_blocking_statuses),
            )
        )
        if existing is not None:
            return ImportOutcome(existing, duplicate=True)
        raise
    _audit(session, batch, uploader_id, "import.created", {"sha256": source_sha256})
    batch.status = ImportStatus.VALIDATING
    _audit(session, batch, uploader_id, "import.validating")
    session.flush()

    try:
        snapshot = parse_osip_workbook(
            blob_store.path_for(storage_key),
            portfolio_code=normalized_portfolio_code,
            source_name=batch.original_filename,
        )
        if snapshot.source_sha256 != source_sha256:
            raise OsipWorkbookError("Хеш сохранённого источника отличается от загруженного содержимого")
        batch.osip_resolved_columns = dict(snapshot.resolved_columns) or None
    except Exception as exc:
        batch.status = ImportStatus.FAILED
        batch.error_message = _safe_error(exc)
        _audit(
            session,
            batch,
            uploader_id,
            "import.failed",
            {"error": batch.error_message},
        )
        session.flush()
        return ImportOutcome(batch)

    # Persistence failures are infrastructure/programming failures, not bad
    # workbook evidence, so they must roll the transaction back at the API edge.
    _persist_snapshot(session, batch, snapshot)
    batch.status = ImportStatus.VALIDATED
    batch.validated_at = utcnow()
    _audit(session, batch, uploader_id, "import.validated")
    session.flush()
    return ImportOutcome(batch)


def _validate_upload(filename: str, content: bytes, max_upload_bytes: int) -> None:
    if not filename or len(filename) > 500:
        raise UploadValidationError("Имя рабочей книги отсутствует или слишком длинное")
    if Path(filename).suffix.lower() != ".xls":
        raise UploadValidationError("Принимаются только рабочие книги OSIP в формате .xls")
    if len(content) > max_upload_bytes:
        raise UploadValidationError(
            f"Размер рабочей книги превышает лимит загрузки {max_upload_bytes} байт"
        )
    if not content.startswith(OLE_SIGNATURE):
        raise UploadValidationError("Рабочая книга не имеет корректной сигнатуры OLE .xls")


def _persist_snapshot(
    session: Session, batch: ImportBatch, snapshot: PortfolioSnapshot
) -> None:
    # Serializing imports per portfolio prevents two simultaneous corrections
    # from selecting the same immutable version number in PostgreSQL.
    session.execute(
        select(Portfolio)
        .where(Portfolio.code == snapshot.portfolio_code)
        .with_for_update()
    ).scalar_one()
    version = (
        session.scalar(
            select(func.max(ImportBatch.version)).where(
                ImportBatch.portfolio_code == snapshot.portfolio_code,
                ImportBatch.report_date == snapshot.report_date,
            )
        )
        or 0
    ) + 1
    batch.portfolio_code = snapshot.portfolio_code
    batch.report_date = snapshot.report_date
    batch.source_report_date = snapshot.report_date
    # The workbook is authoritative for both dates. The filename is retained
    # as evidence only and must never create a synthetic date mismatch.
    batch.business_date = snapshot.report_date
    batch.generated_at = batch.created_at
    batch.version = version

    purchase_amount_kzt = sum(
        (_money(position.purchase_amount_kzt) or ZERO for position in snapshot.positions),
        ZERO,
    )
    derived_carrying_value_kzt = sum(
        (
            _money(position.derived_carrying_value_kzt) or ZERO
            for position in snapshot.positions
        ),
        ZERO,
    )
    cash_kzt = sum(
        (_money(balance.kzt_amount) or ZERO for balance in snapshot.cash_balances), ZERO
    )
    total_fees_kzt = sum(
        (
            (_money(position.organizer_fee_kzt) or ZERO)
            + (_money(position.broker_fee_kzt) or ZERO)
            for position in snapshot.positions
        ),
        ZERO,
    )
    total_reserves_kzt = sum(
        (_money(position.reserve_kzt) or ZERO for position in snapshot.positions), ZERO
    )
    record = PortfolioSnapshotRecord(
        import_batch=batch,
        portfolio_code=snapshot.portfolio_code,
        report_date=snapshot.report_date,
        version=version,
        position_count=len(snapshot.positions),
        unique_isin_count=len(snapshot.unique_isins),
        raw_settlement_count=len(snapshot.raw_settlements),
        settlement_count=len(snapshot.settlements),
        purchase_amount_kzt=purchase_amount_kzt,
        derived_carrying_value_kzt=derived_carrying_value_kzt,
        cash_kzt=cash_kzt,
        derived_operational_total_kzt=derived_carrying_value_kzt + cash_kzt,
        total_fees_kzt=total_fees_kzt,
        total_reserves_kzt=total_reserves_kzt,
    )
    session.add(record)
    session.flush()

    for position in {position.isin: position for position in snapshot.positions}.values():
        normalized_asset_class = _normalized_asset_class(
            position.source_section, position.raw_security_type
        )
        instrument = session.get(InstrumentRecord, position.isin)
        if instrument is None:
            session.add(
                InstrumentRecord(
                    isin=position.isin,
                    security_code=position.security_code,
                    issuer=position.issuer,
                    raw_security_type=position.raw_security_type,
                    normalized_asset_class=normalized_asset_class,
                    instrument_currency=position.instrument_currency,
                    raw_sector=position.raw_sector,
                )
            )
        else:
            # Later imports can correct issuer/sector/classification typos;
            # keep instrument reference data in sync with the most recently
            # parsed snapshot rather than freezing it at first sight.
            instrument.security_code = position.security_code
            instrument.issuer = position.issuer
            instrument.raw_security_type = position.raw_security_type
            instrument.normalized_asset_class = normalized_asset_class
            instrument.instrument_currency = position.instrument_currency
            instrument.raw_sector = position.raw_sector
    session.flush()

    source_rows: dict[tuple[str, int], SourceRow] = {}
    for position in snapshot.positions:
        source_row = _source_row(
            session,
            batch,
            source_rows,
            position.source.sheet_name,
            position.source.row_number,
            "position",
            position.raw_row,
        )
        session.add(
            PositionLotRecord(
                snapshot=record,
                source_row=source_row,
                source_section=position.source_section,
                security_code=position.security_code,
                isin=position.isin,
                raw_security_type=position.raw_security_type,
                issuer=position.issuer,
                valuation_method=position.valuation_method,
                instrument_currency=position.instrument_currency,
                raw_sector=position.raw_sector,
                rating_sp=position.rating_sp,
                rating_moodys=position.rating_moodys,
                rating_fitch=position.rating_fitch,
                coupon_or_repo_rate=position.coupon_or_repo_rate,
                nominal_value=position.nominal_value,
                open_date=position.open_date,
                close_date=position.close_date,
                quantity=position.quantity,
                purchase_date=position.purchase_date,
                purchase_price=position.purchase_price,
                purchase_yield=position.purchase_yield,
                current_ytm=position.current_ytm,
                purchase_amount_native=position.purchase_amount_native,
                purchase_amount_kzt=position.purchase_amount_kzt,
                carrying_amount_native=position.carrying_amount_native,
                carrying_price_native=position.carrying_price_native,
                reserve_kzt=position.reserve_kzt,
                organizer_fee_kzt=position.organizer_fee_kzt,
                broker_fee_kzt=position.broker_fee_kzt,
                accrued_income_kzt=position.accrued_income_kzt,
                principal_indexation=position.principal_indexation,
                report_fx_rate=position.report_fx_rate,
                previous_coupon_date=position.previous_coupon_date,
                next_coupon_date=position.next_coupon_date,
                listing_rating=position.listing_rating,
                derived_carrying_value_kzt=position.derived_carrying_value_kzt,
                expected_coupon_cached=position.expected_coupon_cached,
                unavailable_fields=list(position.unavailable_fields),
            )
        )

    for cash in snapshot.cash_balances:
        source_row = _source_row(
            session,
            batch,
            source_rows,
            cash.source.sheet_name,
            cash.source.row_number,
            "cash",
            cash.raw_row,
        )
        session.add(
            CashBalanceRecord(
                snapshot=record,
                source_row=source_row,
                raw_label=cash.raw_label,
                currency=cash.currency,
                custodian=cash.custodian,
                native_amount=cash.native_amount,
                kzt_amount=cash.kzt_amount,
            )
        )

    raw_by_ref: dict[tuple[str, int], tuple[Any, ...]] = {}
    for settlement in snapshot.raw_settlements:
        for ref, raw_row in zip(settlement.source_refs, settlement.raw_rows, strict=True):
            raw_by_ref[(ref.sheet_name, ref.row_number)] = raw_row

    for settlement in snapshot.settlements:
        settlement_record = SettlementEventRecord(
            snapshot=record,
            signature_hash=_settlement_signature_hash(settlement),
            security_code=settlement.security_code,
            isin=settlement.isin,
            raw_security_type=settlement.raw_security_type,
            issuer=settlement.issuer,
            currency=settlement.currency,
            quantity=settlement.quantity,
            settlement_date=settlement.settlement_date,
            purchase_price=settlement.purchase_price,
            amount_native=settlement.amount_native,
            amount_kzt=settlement.amount_kzt,
        )
        session.add(settlement_record)
        for ref in settlement.source_refs:
            source_row = _source_row(
                session,
                batch,
                source_rows,
                ref.sheet_name,
                ref.row_number,
                "settlement",
                raw_by_ref[(ref.sheet_name, ref.row_number)],
            )
            settlement_record.source_links.append(
                SettlementSourceLink(source_row=source_row)
            )

    for issue in snapshot.issues:
        session.add(
            DataQualityIssueRecord(
                snapshot=record,
                code=issue.code,
                severity=issue.severity.value,
                message=issue.message,
                affected_fields=list(issue.affected_fields),
                source_refs=[
                    {
                        "workbook_name": ref.workbook_name,
                        "sheet_name": ref.sheet_name,
                        "row_number": ref.row_number,
                    }
                    for ref in issue.source_refs
                ],
            )
        )
    session.flush()


def _source_row(
    session: Session,
    batch: ImportBatch,
    source_rows: dict[tuple[str, int], SourceRow],
    sheet_name: str,
    row_number: int,
    row_kind: str,
    raw_row: tuple[Any, ...],
) -> SourceRow:
    key = (sheet_name, row_number)
    if key not in source_rows:
        row = SourceRow(
            import_batch=batch,
            workbook_name=batch.original_filename,
            sheet_name=sheet_name,
            row_number=row_number,
            row_kind=row_kind,
            parser_version=batch.parser_version,
            raw_values=[_json_value(value) for value in raw_row],
        )
        session.add(row)
        source_rows[key] = row
    return source_rows[key]


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _money(value: Decimal | None) -> Decimal | None:
    return value.quantize(MONEY_QUANTUM) if value is not None else None


def _normalized_asset_class(source_section: str, raw_security_type: str) -> str:
    section = source_section.casefold()
    security_type = raw_security_type.casefold()
    if "etf" in section:
        return "ETF"
    if "репо" in section or "репо" in security_type:
        return "Repo"
    if "гцб" in section or security_type == "гцб":
        return "Government bond"
    if "облигац" in security_type:
        return "Corporate bond"
    if "акци" in security_type:
        return "Equity"
    return raw_security_type or "Not supplied"


def _settlement_signature_hash(settlement: SettlementEvent) -> str:
    canonical = [_json_value(value) for value in settlement.signature]
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, (OsipWorkbookError, ValueError)):
        return str(exc)[:2000]
    return f"{type(exc).__name__}: workbook parsing failed"[:2000]


def _audit(
    session: Session,
    batch: ImportBatch,
    actor_id: str,
    action: str,
    detail: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            import_batch=batch,
            actor_id=actor_id,
            action=action,
            detail=detail or {},
        )
    )
