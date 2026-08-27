"""Published-snapshot (overview/holdings/allocations/DQ/calendar) HTTP handlers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from osip_dashboard.api_schemas import DqAssignmentRequest
from osip_dashboard.identity import require_domain, require_portfolio, require_role
from osip_dashboard.persistence.models import (
    AuditEvent,
    DataQualityIssueRecord,
    ImportBatch,
    ImportStatus,
    PortfolioSnapshotRecord,
    SourceRow,
    utcnow,
)
from osip_dashboard.services.holdings_export import (
    create_cash_calendar_xlsx,
    create_dq_issues_xlsx,
    create_holdings_xlsx,
    create_lots_xlsx,
    estimated_coupon_income_kzt,
    estimated_paid_coupon_income_native,
    expected_coupon_native,
    is_coupon_bearing_lot,
    lot_maturity_amount_native,
)
from osip_dashboard.services.instrument_dictionary import instrument_class, true_asset_class
from osip_dashboard.services.dividends import (
    dividend_data_status,
    load_dividend_history,
    lot_dividend_contribution,
)
from osip_dashboard.services.hpr import hpr_percent
from osip_dashboard.services.workflow import (
    Actor,
    WorkflowError,
    assign_dq_issue as assign_dq_issue_service,
    get_dq_issue_or_error,
)
from osip_dashboard.i18n import localize_dq_issue, request_language, workflow_message
from datetime import date

from .shared import (
    ActorDep,
    SessionDep,
    XlsxResponse,
    _decimal,
    _dividend_status_payload,
    _excel_column_letter,
    _get_snapshot,
    _iso,
    _osip_export_filename,
    _snapshot_summary,
    router,
)


@router.get("/snapshots/{snapshot_id}/overview")
def snapshot_overview(
    snapshot_id: UUID, session: SessionDep, actor: ActorDep
) -> dict[str, Any]:
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    # A derived total is only meaningful for lots that have the two mandatory
    # inputs (AA carrying amount and AU report FX rate). Excluding an
    # incomplete lot - rather than either fabricating it as zero (silently
    # understating the total) or blanking the whole portfolio's total over
    # one bad lot (previously: any single incomplete lot, e.g. one deposit
    # with no current-balance mark, made the entire card read "Unavailable"
    # even though every other lot was fine) - gives a real, honest partial
    # total, with the gap disclosed via excluded_lot_count/
    # excluded_purchase_value_kzt instead of hidden either way.
    incomplete_lots = [lot for lot in snapshot.position_lots if lot.derived_carrying_value_kzt is None]
    carrying_value = sum(
        (lot.derived_carrying_value_kzt for lot in snapshot.position_lots if lot.derived_carrying_value_kzt is not None),
        Decimal("0"),
    )
    excluded_purchase_value = sum(
        (lot.purchase_amount_kzt or Decimal("0") for lot in incomplete_lots), Decimal("0")
    )
    cash_value = sum(
        (balance.kzt_amount for balance in snapshot.cash_balances), Decimal("0")
    )
    purchase_value = sum(
        (lot.purchase_amount_kzt or Decimal("0") for lot in snapshot.position_lots),
        Decimal("0"),
    )
    return {
        **_snapshot_summary(snapshot),
        "data_label": "operational/derived",
        "excluded_lot_count": len(incomplete_lots),
        "excluded_purchase_value_kzt": _decimal(excluded_purchase_value) if incomplete_lots else None,
        # One row per excluded lot, not just a count or a bare code list -
        # the web page's own "Excluded: N" button opens a dedicated view
        # built from this (not the full metric-provenance drawer, which
        # buries these among every complete lot's own references too).
        "excluded_lots": [
            {
                "security_code": lot.security_code,
                "isin": lot.isin,
                "issuer": lot.issuer,
                "purchase_amount_kzt": _decimal(lot.purchase_amount_kzt or Decimal("0")),
                "missing_fields": [
                    field for field in ("carrying_amount_native", "report_fx_rate")
                    if getattr(lot, field) is None
                ],
            }
            for lot in incomplete_lots
        ],
        "metrics": {
            "position_count": _metric(snapshot.position_count, "source"),
            "unique_isin_count": _metric(snapshot.unique_isin_count, "source"),
            "purchase_amount_kzt": _metric(purchase_value, "source"),
            "derived_carrying_value_kzt": _metric(carrying_value, "derived"),
            "cash_kzt": _metric(cash_value, "source"),
            "derived_operational_total_kzt": _metric(carrying_value + cash_value, "derived"),
            "total_fees_kzt": _metric(snapshot.total_fees_kzt, "source"),
            "total_reserves_kzt": _metric(snapshot.total_reserves_kzt, "source"),
            "official_nav_kzt": _metric(None, "unavailable"),
            "official_performance": _metric(None, "unavailable"),
        },
    }


def _provenance_ref(source_row, batch: ImportBatch, field: str, value: Any, note: str | None = None) -> dict[str, Any]:
    """Return a source reference with the field/value that fed a metric.

    The row identity is the immutable evidence key; field and value make the
    reference useful to a portfolio manager without exposing the whole raw row.
    """
    reference = _source_payload(source_row, batch)
    column = _osip_source_column(field, source_row.sheet_name, batch)
    if column is not None:
        reference.update({
            "source_column": column,
            "source_column_letter": _excel_column_letter(column),
            "source_cell": f"{_excel_column_letter(column)}{source_row.row_number}",
            "source_kind": "row",
        })
    else:
        # Synthetic fields (for example a lot-count metric) identify the
        # source row but do not correspond to one physical workbook cell.
        reference["source_kind"] = "row"
    reference.update({"field": field, "value": _decimal(value) if isinstance(value, Decimal) else (str(value) if value is not None else None)})
    if note:
        reference["note"] = note
    return reference


# Physical one-based columns in the canonical ОСИП_ПОРТФЕЛЬ sheet.  These are
# Fallback ONLY for imports that predate ImportBatch.osip_resolved_columns
# (every import in this app's history up to 2026-08, all parsed under this
# exact layout - confirmed by checking every existing published snapshot).
# A current import's own resolved column map (persisted per-batch by
# ingestion/osip_workbook.py's _resolve_columns, since the generator's
# column layout is not actually stable - see the 2026-08 change that broke
# a fixed positional map like this one) always takes precedence; see
# _osip_source_column below.
_OSIP_SOURCE_COLUMNS: dict[str, int] = {
    "raw_sector": 5,                 # E
    "rating_sp": 2,                  # B
    "rating_moodys": 3,              # C
    "rating_fitch": 4,               # D
    "security_code": 6,              # F
    "isin": 7,                       # G
    "raw_security_type": 8,          # H
    "issuer": 9,                     # I
    "valuation_method": 10,          # J
    "coupon_or_repo_rate": 11,       # K
    "nominal_value": 12,             # L
    "instrument_currency": 13,      # M
    "open_date": 14,                 # N
    "close_date": 15,                # O
    "quantity": 17,                  # Q
    "purchase_date": 18,             # R
    "purchase_price": 19,            # S
    "purchase_yield": 20,            # T
    "purchase_amount_native": 21,    # U
    "purchase_amount_kzt": 22,       # V
    "current_ytm": 26,               # Z
    "carrying_amount_native": 27,    # AA
    "reserve_kzt": 30,               # AD
    "organizer_fee_kzt": 31,         # AE
    "broker_fee_kzt": 32,            # AF
    "previous_coupon_date": 38,      # AL
    "next_coupon_date": 39,          # AM
    "accrued_income_kzt": 44,        # AR
    "principal_indexation": 46,      # AT
    "report_fx_rate": 47,            # AU
    "listing_rating": 59,            # BG
    # Cash rows use the same OSIP sheet but have their own source fields.
    "raw_label": 1,                  # A
    "native_amount": 27,             # AA
    "kzt_amount": 28,                # AB
}


# Provenance field names (matching PositionLotSnapshot's own attribute
# names) that differ from ingestion's internal _FIELD_LABELS key for the
# same cell, plus the cash-row fields that reuse a position field's column.
_OSIP_RESOLVED_COLUMN_ALIASES: dict[str, str] = {
    "raw_security_type": "security_type",
    "native_amount": "carrying_amount_native",
    "kzt_amount": "official_carrying_value_kzt",
}


def _osip_source_column(field: str, sheet_name: str | None, batch: ImportBatch | None = None) -> int | None:
    if sheet_name != "ОСИП_ПОРТФЕЛЬ":
        return None
    # Column A (the section/label anchor) never moves regardless of layout
    # revision - it doubles as the row-classification column for every row,
    # not just cash rows, so it's excluded from the per-import resolved map.
    if field == "raw_label":
        return 1
    resolved = getattr(batch, "osip_resolved_columns", None) if batch is not None else None
    if resolved:
        column = resolved.get(_OSIP_RESOLVED_COLUMN_ALIASES.get(field, field))
        if column is not None:
            # resolved columns are zero-based (ingestion's own convention);
            # every column here is one-based (matches _excel_column_letter).
            return column + 1
    return _OSIP_SOURCE_COLUMNS.get(field)


def snapshot_provenance(
    snapshot_id: UUID, session: SessionDep, actor: ActorDep
) -> dict[str, Any]:
    """Return auditable lineage for every overview metric.

    Source metrics point to the exact workbook row and parsed field. Derived
    metrics include their formula and the source inputs used by that formula.
    """
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    batch = snapshot.import_batch
    lots = list(snapshot.position_lots)
    cash = list(snapshot.cash_balances)

    def refs_for_lots(field: str, value_attr: str, note: str | None = None) -> list[dict[str, Any]]:
        return [_provenance_ref(lot.source_row, batch, field, getattr(lot, value_attr), note) for lot in lots]

    def refs_for_cash(field: str, value_attr: str, note: str | None = None) -> list[dict[str, Any]]:
        return [_provenance_ref(item.source_row, batch, field, getattr(item, value_attr), note) for item in cash]

    carrying_refs: list[dict[str, Any]] = []
    for lot in lots:
        carrying_refs.extend([
            _provenance_ref(lot.source_row, batch, "carrying_amount_native", lot.carrying_amount_native),
            _provenance_ref(lot.source_row, batch, "report_fx_rate", lot.report_fx_rate),
            _provenance_ref(lot.source_row, batch, "principal_indexation", lot.principal_indexation, "Пусто означает коэффициент 1"),
            _provenance_ref(lot.source_row, batch, "accrued_income_kzt", lot.accrued_income_kzt, "Пусто означает начисление 0"),
        ])
    incomplete_lots = [lot for lot in lots if lot.derived_carrying_value_kzt is None]
    carrying = sum(
        (lot.derived_carrying_value_kzt for lot in lots if lot.derived_carrying_value_kzt is not None),
        Decimal("0"),
    )
    cash_value = sum((item.kzt_amount for item in cash), Decimal("0"))
    purchase = sum((lot.purchase_amount_kzt or Decimal("0") for lot in lots), Decimal("0"))
    operational = carrying + cash_value
    excluded_purchase_value = sum(
        (lot.purchase_amount_kzt or Decimal("0") for lot in incomplete_lots), Decimal("0")
    )
    exclusion_note = (
        f" Excluded, for lacking a carrying amount or report FX rate: {', '.join(lot.security_code for lot in incomplete_lots)} "
        f"(totaling {excluded_purchase_value:,.2f} KZT by purchase amount) - see the missing inputs below."
        if incomplete_lots else ""
    )
    incomplete_refs = [
        _provenance_ref(
            lot.source_row,
            batch,
            field,
            getattr(lot, field),
            "Required input is blank; the derived total is unavailable.",
        )
        for lot in incomplete_lots
        for field in ("carrying_amount_native", "report_fx_rate")
        if getattr(lot, field) is None
    ]

    metrics: dict[str, dict[str, Any]] = {
        "position_count": {"code": "position_count", "label": "Current lots", "basis": "source", "value": snapshot.position_count, "explanation": "Count of persisted OSIP position lots; one lot maps to one source row.", "source_refs": refs_for_lots("position_lot", "quantity")},
        "unique_isin_count": {"code": "unique_isin_count", "label": "Unique instruments", "basis": "source", "value": snapshot.unique_isin_count, "explanation": "Count of distinct ISINs in the persisted position lots.", "source_refs": refs_for_lots("isin", "isin")},
        "purchase_amount_kzt": {"code": "purchase_amount_kzt", "label": "Purchase amount", "basis": "source", "value": _decimal(purchase), "explanation": "Sum of the parsed purchase_amount_kzt field for all included lots.", "source_refs": refs_for_lots("purchase_amount_kzt", "purchase_amount_kzt")},
        "derived_carrying_value_kzt": {"code": "derived_carrying_value_kzt", "label": "Derived carrying value", "basis": "derived", "value": _decimal(carrying), "formula": "carrying_amount_native × report_fx_rate × principal_indexation + accrued_income_kzt (per lot), summed over lots with a carrying amount", "explanation": f"Operational/derived value calculated from the listed source fields; it is not official NAV.{exclusion_note}", "source_refs": carrying_refs + incomplete_refs},
        "cash_kzt": {"code": "cash_kzt", "label": "Cash equivalent", "basis": "source", "value": _decimal(cash_value), "explanation": "Sum of parsed KZT cash equivalents from the cash balance rows.", "source_refs": refs_for_cash("kzt_amount", "kzt_amount")},
        "derived_operational_total_kzt": {"code": "derived_operational_total_kzt", "label": "Operational total", "basis": "derived", "value": _decimal(operational), "formula": "derived_carrying_value_kzt + cash_kzt", "explanation": f"Operational total combines the derived carrying value and source cash equivalent; it is not NAV or market value.{exclusion_note}", "source_refs": carrying_refs + incomplete_refs + refs_for_cash("kzt_amount", "kzt_amount"), "inputs": [{"code": "derived_carrying_value_kzt", "label": "Derived carrying value", "value": _decimal(carrying), "basis": "derived", "source_refs": carrying_refs + incomplete_refs}, {"code": "cash_kzt", "label": "Cash equivalent", "value": _decimal(cash_value), "basis": "source", "source_refs": refs_for_cash("kzt_amount", "kzt_amount")} ]},
        "total_fees_kzt": {"code": "total_fees_kzt", "label": "Fees", "basis": "source", "value": _decimal(snapshot.total_fees_kzt), "explanation": "Sum of parsed organizer_fee_kzt and broker_fee_kzt fields for all included lots.", "source_refs": refs_for_lots("organizer_fee_kzt", "organizer_fee_kzt") + refs_for_lots("broker_fee_kzt", "broker_fee_kzt")},
        "total_reserves_kzt": {"code": "total_reserves_kzt", "label": "Recognised reserves", "basis": "source", "value": _decimal(snapshot.total_reserves_kzt), "explanation": "Sum of the parsed reserve_kzt field for all included lots.", "source_refs": refs_for_lots("reserve_kzt", "reserve_kzt")},
        "official_nav_kzt": {"code": "official_nav_kzt", "label": "Official NAV", "basis": "unavailable", "value": None, "explanation": "The OSIP workbook does not provide an approved official NAV series and its required valuation controls.", "source_refs": []},
        "official_performance": {"code": "official_performance", "label": "Official performance", "basis": "unavailable", "value": None, "explanation": "Historical approved NAV, cash flows, and benchmark data required for official performance are not present in this snapshot.", "source_refs": []},
    }
    return {"snapshot_id": str(snapshot.id), "portfolio": snapshot.portfolio_code, "report_date": _iso(snapshot.report_date), "version": snapshot.version, "source_filename": batch.original_filename, "metrics": metrics}


@router.get("/snapshots/{snapshot_id}/holdings")
def snapshot_holdings(
    snapshot_id: UUID,
    session: SessionDep,
    actor: ActorDep,
    view: Literal["lots", "instruments"] = Query("lots"),
) -> dict[str, Any]:
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    if view == "instruments":
        return {
            "snapshot_id": str(snapshot.id),
            "view": "instruments",
            "value_basis": "derived_carrying_value_kzt",
            "items": _aggregated_holdings(snapshot),
            "dividend_data_status": _dividend_status_payload(dividend_data_status()),
        }
    return {
        "snapshot_id": str(snapshot.id),
        "view": "lots",
        "dividend_data_status": _dividend_status_payload(dividend_data_status()),
        "items": [
            {
                "id": str(lot.id),
                "source": _source_payload(
                    lot.source_row,
                    snapshot.import_batch,
                    "quantity",
                    lot.quantity,
                    "Количество лота из строки позиции",
                ),
                "source_section": lot.source_section,
                "security_code": lot.security_code,
                "isin": lot.isin,
                "raw_security_type": lot.raw_security_type,
                "normalized_asset_class": lot.instrument.normalized_asset_class,
                "issuer": lot.issuer,
                "valuation_method": lot.valuation_method,
                "instrument_currency": lot.instrument_currency,
                "raw_sector": lot.raw_sector,
                "rating_sp": lot.rating_sp,
                "rating_moodys": lot.rating_moodys,
                "rating_fitch": lot.rating_fitch,
                "coupon_or_repo_rate": _decimal(lot.coupon_or_repo_rate),
                "nominal_value": _decimal(lot.nominal_value),
                "open_date": _iso(lot.open_date),
                "close_date": _iso(lot.close_date),
                "quantity": _decimal(lot.quantity),
                "purchase_date": _iso(lot.purchase_date),
                "purchase_price": _decimal(lot.purchase_price),
                "purchase_yield": _decimal(lot.purchase_yield),
                "current_ytm": _decimal(lot.current_ytm),
                "purchase_amount_native": _decimal(lot.purchase_amount_native),
                "purchase_amount_kzt": _decimal(lot.purchase_amount_kzt),
                "carrying_amount_native": _decimal(lot.carrying_amount_native),
                "carrying_price_native": _decimal(lot.carrying_price_native),
                "reserve_kzt": _decimal(lot.reserve_kzt),
                "organizer_fee_kzt": _decimal(lot.organizer_fee_kzt),
                "broker_fee_kzt": _decimal(lot.broker_fee_kzt),
                "report_fx_rate": _decimal(lot.report_fx_rate),
                "principal_indexation": _decimal(lot.principal_indexation),
                "accrued_income_kzt": _decimal(lot.accrued_income_kzt),
                "previous_coupon_date": _iso(lot.previous_coupon_date),
                "next_coupon_date": _iso(lot.next_coupon_date),
                "listing_rating": lot.listing_rating or None,
                "derived_carrying_value_kzt": _decimal(
                    lot.derived_carrying_value_kzt
                ),
                "unavailable_fields": lot.unavailable_fields,
            }
            for lot in snapshot.position_lots
        ],
    }


@router.get("/snapshots/{snapshot_id}/holdings/export")
def export_snapshot_holdings(
    snapshot_id: UUID,
    session: SessionDep,
    actor: ActorDep,
    basis: Literal["derived_carrying", "purchase"] = Query("derived_carrying"),
    term: str = Query("", max_length=200),
    asset_class: str | None = Query(None, max_length=100),
) -> XlsxResponse:
    """Download the ISIN-keyed instrument table and reconciled distributions."""
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    if snapshot.import_batch.status != ImportStatus.PUBLISHED:
        raise HTTPException(
            status_code=409,
            detail="Выгрузка доступна только для опубликованной версии портфеля",
        )

    normalized_term = term.strip()
    normalized_asset_class = asset_class.strip() if asset_class else None
    items = _filter_instrument_holdings(
        _aggregated_holdings(snapshot, include_internal=True),
        term=normalized_term,
        asset_class=normalized_asset_class,
    )
    content = create_holdings_xlsx(
        snapshot,
        items,
        basis=basis,
        term=normalized_term,
        asset_class=normalized_asset_class,
    )
    filename = _osip_export_filename("holdings", snapshot.portfolio_code, snapshot.report_date)
    session.add(
        AuditEvent(
            import_batch=snapshot.import_batch,
            actor_id=actor.actor_id,
            action="holdings.exported",
            detail={
                "format": "xlsx",
                "basis": basis,
                "term": normalized_term,
                "asset_class": normalized_asset_class,
                "row_count": len(items),
                "filename": filename,
            },
        )
    )
    session.commit()
    return XlsxResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/snapshots/{snapshot_id}/lots/export")
def export_snapshot_lots(
    snapshot_id: UUID, session: SessionDep, actor: ActorDep
) -> XlsxResponse:
    """Download the immutable source-lot detail for a published snapshot."""
    require_role(actor, "reader")
    snapshot = _published_snapshot_or_error(session, snapshot_id, actor)
    content = create_lots_xlsx(snapshot)
    filename = _osip_export_filename("lots", snapshot.portfolio_code, snapshot.report_date)
    _record_snapshot_export(
        session, snapshot, actor, "lots.exported", filename, {"row_count": len(snapshot.position_lots)}
    )
    return XlsxResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/snapshots/{snapshot_id}/allocations")
def snapshot_allocations(
    snapshot_id: UUID,
    session: SessionDep,
    actor: ActorDep,
    dimension: Literal[
        "asset_class",
        "currency",
        "issuer",
        "valuation_method",
        "raw_sector",
        "rating",
    ] = Query("asset_class"),
    basis: Literal["derived_carrying", "purchase"] = Query("derived_carrying"),
) -> dict[str, Any]:
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    groups: dict[str, dict[str, Any]] = {}
    excluded_value_kzt = Decimal("0")
    excluded_lot_count = 0
    for lot in snapshot.position_lots:
        label = _allocation_label(lot, dimension)
        group = groups.setdefault(
            label,
            {
                "label": label,
                "value_kzt": Decimal("0"),
                "lot_count": 0,
                "isins": set(),
            },
        )
        lot_value = lot.purchase_amount_kzt if basis == "purchase" else lot.derived_carrying_value_kzt
        if lot_value is None:
            # A lot with no derived carrying value (e.g. a source-reported
            # deposit with no current balance mark) must not fold into this
            # dimension's total as zero - that silently drops real,
            # purchase-confirmed money from the allocation chart instead of
            # disclosing that it's missing. Purchase basis never hits this:
            # purchase_amount_kzt is populated for every lot.
            excluded_value_kzt += lot.purchase_amount_kzt or Decimal("0")
            excluded_lot_count += 1
        else:
            group["value_kzt"] += lot_value
        group["lot_count"] += 1
        group["isins"].add(lot.isin)
    total = sum((group["value_kzt"] for group in groups.values()), Decimal("0"))
    items = [
        {
            "label": group["label"],
            "value_kzt": _decimal(group["value_kzt"]),
            "weight_percent": _percentage(group["value_kzt"], total),
            "lot_count": group["lot_count"],
            "instrument_count": len(group["isins"]),
        }
        for group in groups.values()
    ]
    items.sort(key=lambda item: Decimal(item["value_kzt"] or "0"), reverse=True)
    return {
        "snapshot_id": str(snapshot.id),
        "dimension": dimension,
        "value_basis": "purchase_amount_kzt"
        if basis == "purchase"
        else "derived_carrying_value_kzt",
        "total_value_kzt": _decimal(total),
        "items": items,
        "excluded_value_kzt": _decimal(excluded_value_kzt) if excluded_lot_count else None,
        "excluded_lot_count": excluded_lot_count,
    }


@router.get("/snapshots/{snapshot_id}/cash")
def snapshot_cash(
    snapshot_id: UUID, session: SessionDep, actor: ActorDep
) -> dict[str, Any]:
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    return {
        "snapshot_id": str(snapshot.id),
        "items": [
            {
                "id": str(item.id),
                "source": _source_payload(
                    item.source_row,
                    snapshot.import_batch,
                    "kzt_amount",
                    item.kzt_amount,
                    "Сумма в тенге из строки денежных средств",
                ),
                "raw_label": item.raw_label,
                "currency": item.currency,
                "custodian": item.custodian,
                "native_amount": _decimal(item.native_amount),
                "kzt_amount": _decimal(item.kzt_amount),
                "active": item.native_amount != 0 or item.kzt_amount != 0,
            }
            for item in snapshot.cash_balances
        ],
    }


@router.get("/snapshots/{snapshot_id}/cash-calendar/export")
def export_snapshot_cash_calendar(
    snapshot_id: UUID,
    session: SessionDep,
    actor: ActorDep,
    request: Request,
    include_inactive: bool = Query(False),
) -> XlsxResponse:
    """Download cash and the OSIP operational calendar in one workbook."""
    require_role(actor, "reader")
    snapshot = _published_snapshot_or_error(session, snapshot_id, actor)
    cash_items = snapshot_cash(snapshot_id, session, actor)["items"]
    calendar_items = snapshot_calendar(snapshot_id, session, actor, request)["items"]
    content = create_cash_calendar_xlsx(
        snapshot, cash_items, calendar_items, include_inactive=include_inactive
    )
    filename = _osip_export_filename("cash_calendar", snapshot.portfolio_code, snapshot.report_date)
    _record_snapshot_export(
        session,
        snapshot,
        actor,
        "cash_calendar.exported",
        filename,
        {
            "include_inactive": include_inactive,
            "cash_row_count": len(cash_items) if include_inactive else sum(item["active"] for item in cash_items),
            "calendar_row_count": len(calendar_items),
        },
    )
    return XlsxResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/snapshots/{snapshot_id}/settlements")
def snapshot_settlements(
    snapshot_id: UUID, session: SessionDep, actor: ActorDep
) -> dict[str, Any]:
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    return {
        "snapshot_id": str(snapshot.id),
        "raw_count": snapshot.raw_settlement_count,
        "deduplicated_count": snapshot.settlement_count,
        "items": [
            {
                "id": str(item.id),
                "security_code": item.security_code,
                "isin": item.isin,
                "raw_security_type": item.raw_security_type,
                "issuer": item.issuer,
                "currency": item.currency,
                "quantity": _decimal(item.quantity),
                "settlement_date": _iso(item.settlement_date),
                "purchase_price": _decimal(item.purchase_price),
                "amount_native": _decimal(item.amount_native),
                "amount_kzt": _decimal(item.amount_kzt),
                "source_refs": [
                    ref
                    for link in item.source_links
                    for ref in (
                        _source_payload(
                            link.source_row,
                            snapshot.import_batch,
                            "settlement_date",
                            item.settlement_date,
                        ),
                        _source_payload(
                            link.source_row,
                            snapshot.import_batch,
                            "amount_kzt",
                            item.amount_kzt,
                        )
                        if item.amount_kzt is not None
                        else None,
                    )
                    if ref is not None
                ],
            }
            for item in snapshot.settlements
        ],
    }


@router.get("/snapshots/{snapshot_id}/issues")
def snapshot_issues(
    snapshot_id: UUID, session: SessionDep, actor: ActorDep, request: Request
) -> dict[str, Any]:
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    return _snapshot_issues_payload(session, snapshot, request_language(request))


def _snapshot_issues_payload(
    session: Session, snapshot: PortfolioSnapshotRecord, language: str = "ru"
) -> dict[str, Any]:
    batch = snapshot.import_batch
    row_lookup = {
        (row.sheet_name, row.row_number): str(row.id)
        for row in session.execute(
            select(SourceRow).where(SourceRow.import_id == snapshot.import_id)
        ).scalars()
    }

    def issue_sources(issue: DataQualityIssueRecord) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for raw in issue.source_refs:
            reference = dict(raw)
            fields = issue.affected_fields or []
            columns = [
                _excel_column_letter(column)
                for field in fields
                if (column := _osip_source_column(field, reference.get("sheet_name"), batch)) is not None
            ]
            if columns:
                row = reference.get("row_number")
                reference["source_columns"] = columns
                reference["source_cells"] = [f"{column}{row}" for column in columns if row is not None]
            reference["source_row_id"] = row_lookup.get(
                (reference.get("sheet_name"), reference.get("row_number"))
            )
            enriched.append(reference)
        return enriched

    return {
        "snapshot_id": str(snapshot.id),
        "items": [
            {
                "id": str(issue.id),
                "code": issue.code,
                "severity": issue.severity,
                "message": localize_dq_issue(issue.code, issue.message, language),
                "affected_fields": issue.affected_fields,
                "source_refs": issue_sources(issue),
                "acknowledgement": {
                    "actor_id": issue.acknowledgement.actor_id,
                    "comment": issue.acknowledgement.comment,
                    "acknowledged_at": _iso(issue.acknowledgement.acknowledged_at),
                }
                if issue.acknowledgement
                else None,
                "owner_id": issue.owner_id,
                "due_date": _iso(issue.due_date),
                "is_overdue": _is_overdue(issue),
            }
            for issue in snapshot.issues
        ],
    }


@router.get("/snapshots/{snapshot_id}/issues/export")
def export_snapshot_issues(
    snapshot_id: UUID,
    session: SessionDep,
    actor: ActorDep,
    term: str = Query("", max_length=200),
    severity: Literal["all", "blocker", "high", "medium", "low"] = Query("all"),
) -> XlsxResponse:
    """Download the exact filtered data-quality view for a published snapshot."""
    require_role(actor, "reader")
    snapshot = _published_snapshot_or_error(session, snapshot_id, actor)
    normalized_term = term.strip()
    # Excel files are deliberately kept in Russian, irrespective of the UI locale.
    issues = _filter_dq_issues(_snapshot_issues_payload(session, snapshot)["items"], normalized_term, severity)
    content = create_dq_issues_xlsx(snapshot, issues, term=normalized_term, severity=severity)
    filename = _osip_export_filename("dq_issues", snapshot.portfolio_code, snapshot.report_date)
    _record_snapshot_export(
        session,
        snapshot,
        actor,
        "dq_issues.exported",
        filename,
        {"term": normalized_term, "severity": severity, "row_count": len(issues)},
    )
    return XlsxResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/issues/{issue_id}/assign")
def assign_dq_issue(
    issue_id: UUID,
    body: DqAssignmentRequest,
    session: SessionDep,
    actor: ActorDep,
) -> dict[str, Any]:
    require_role(actor, "reviewer")
    _get_dq_issue(session, issue_id, actor)
    try:
        due_date = date.fromisoformat(body.due_date) if body.due_date else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Некорректная дата срока устранения") from exc
    try:
        issue = assign_dq_issue_service(
            session, issue_id,
            actor=actor, owner_id=body.owner_id, due_date=due_date, reason=body.reason,
        )
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": str(issue.id),
        "owner_id": issue.owner_id,
        "due_date": _iso(issue.due_date),
        "is_overdue": _is_overdue(issue),
    }


@router.get("/snapshots/{snapshot_id}/calendar")
def snapshot_calendar(
    snapshot_id: UUID, session: SessionDep, actor: ActorDep, request: Request
) -> dict[str, Any]:
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    events: list[dict[str, Any]] = []
    for settlement in snapshot.settlements:
        if settlement.settlement_date is None:
            continue
        events.append(
            {
                "id": f"settlement:{settlement.id}",
                "event_type": "settlement",
                "event_date": settlement.settlement_date.isoformat(),
                "status": "overdue"
                if settlement.settlement_date < snapshot.report_date
                else "upcoming",
                "isin": settlement.isin,
                "security_code": settlement.security_code,
                "title": f"Settlement — {settlement.security_code or settlement.isin}",
                "amount_native": _decimal(settlement.amount_native),
                "amount_kzt": _decimal(settlement.amount_kzt),
                "currency": settlement.currency,
                "amount_basis": "source; settlement currency semantics unconfirmed",
                "source_refs": [
                    _source_payload(link.source_row, snapshot.import_batch)
                    for link in settlement.source_links
                ],
            }
        )
    for lot in snapshot.position_lots:
        lot_events = [
            (
                "repo_open",
                lot.purchase_date or lot.open_date,
            )
            if lot.instrument.normalized_asset_class == "Repo"
            else ("instrument_open", lot.purchase_date or lot.open_date),
            ("repo_close", lot.close_date)
            if lot.instrument.normalized_asset_class == "Repo"
            else ("maturity", lot.close_date),
            ("previous_coupon", lot.previous_coupon_date),
            ("next_coupon", lot.next_coupon_date),
        ]
        for event_type, event_date in lot_events:
            if event_date is None:
                continue
            is_purchase = event_type in {"repo_open", "instrument_open"}
            # Reuse the same maturity/coupon amount computations the Expected
            # Cash Flows export sheet uses (holdings_export.py) - this view
            # used to leave these two event types permanently "Недоступно"
            # even though that sheet demonstrably can and does derive real
            # amounts for the exact same events. No KZT conversion is
            # attempted here, matching that sheet's own scope (native
            # currency only).
            derived_amount_native = None
            derived_basis = None
            if event_type in {"maturity", "repo_close"}:
                derived_amount_native = lot_maturity_amount_native(lot)
                derived_basis = "derived_maturity_amount" if derived_amount_native is not None else None
            elif event_type == "next_coupon":
                derived_amount_native = expected_coupon_native(lot)
                derived_basis = "derived_expected_coupon" if derived_amount_native is not None else None
            events.append(
                {
                    "id": f"{event_type}:{lot.id}",
                    "event_type": event_type,
                    "event_date": event_date.isoformat(),
                    "status": "historical"
                    if event_date < snapshot.report_date
                    else "upcoming",
                    "isin": lot.isin,
                    "security_code": lot.security_code,
                    "title": f"{event_type.replace('_', ' ').title()} — {lot.security_code or lot.isin}",
                    "amount_native": _decimal(lot.purchase_amount_native)
                    if is_purchase
                    else _decimal(derived_amount_native),
                    "amount_kzt": _decimal(lot.purchase_amount_kzt)
                    if is_purchase
                    else None,
                    "currency": lot.instrument_currency,
                    "amount_basis": "source_purchase_amount"
                    if is_purchase and lot.purchase_amount_kzt is not None
                    else derived_basis or "unavailable",
                    "source_refs": [
                        ref
                        for ref in (
                            _source_payload(
                                lot.source_row,
                                snapshot.import_batch,
                                (
                                    "purchase_date"
                                    if event_type in {"repo_open", "instrument_open"} and lot.purchase_date is not None
                                    else "open_date"
                                    if event_type in {"repo_open", "instrument_open"}
                                    else "close_date"
                                    if event_type in {"repo_close", "maturity"}
                                    else "previous_coupon_date"
                                    if event_type == "previous_coupon"
                                    else "next_coupon_date"
                                ),
                                event_date,
                            ),
                            _source_payload(
                                lot.source_row,
                                snapshot.import_batch,
                                "purchase_amount_kzt",
                                lot.purchase_amount_kzt,
                            )
                            if is_purchase and lot.purchase_amount_kzt is not None
                            else None,
                        )
                        if ref is not None
                    ],
                }
            )
    events.sort(key=lambda event: (event["event_date"], event["event_type"], event["id"]))
    return {
        "snapshot_id": str(snapshot.id),
        "report_date": snapshot.report_date.isoformat(),
        "counts": {
            "total": len(events),
            "upcoming": sum(event["status"] == "upcoming" for event in events),
            "overdue_settlements": sum(
                event["event_type"] == "settlement" and event["status"] == "overdue"
                for event in events
            ),
        },
        "settlement_total": {
            "value": None,
            "basis": "unavailable",
            "reason": workflow_message("settlement_amount_unavailable", request_language(request)),
        },
        "items": events,
    }


@router.get("/snapshots/{snapshot_id}/report-readiness")
def snapshot_report_readiness(
    snapshot_id: UUID, session: SessionDep, actor: ActorDep, request: Request
) -> dict[str, Any]:
    require_role(actor, "reader")
    snapshot = _get_snapshot(session, snapshot_id, actor)
    batch = snapshot.import_batch
    critical = [
        issue for issue in snapshot.issues if issue.severity in {"blocker", "high"}
    ]
    unacknowledged = [issue for issue in critical if issue.acknowledgement is None]
    independently_approved = bool(
        batch.reviewer_id and batch.reviewer_id != batch.uploader_id
    )
    is_published = batch.status == ImportStatus.PUBLISHED
    source_first = request.app.state.settings.source_first_mode
    operational_ready = is_published and (
        source_first or (independently_approved and not unacknowledged)
    )
    blocking_reasons: list[str] = []
    language = request_language(request)
    if not is_published:
        blocking_reasons.append(workflow_message("snapshot_not_published", language))
    if not source_first and not independently_approved:
        blocking_reasons.append(workflow_message("independent_approval_missing", language))
    if not source_first and unacknowledged:
        blocking_reasons.append(
            workflow_message("unacknowledged_dq", language, codes=", ".join(sorted({issue.code for issue in unacknowledged})))
        )
    return {
        "snapshot_id": str(snapshot.id),
        "import_id": str(batch.id),
        "portfolio": snapshot.portfolio_code,
        "report_date": snapshot.report_date.isoformat(),
        "version": snapshot.version,
        "status": batch.status.value,
        "source": {
            "filename": batch.original_filename,
            "sha256": batch.source_sha256,
            "parser_version": batch.parser_version,
        },
        "gates": {
            # In trusted local mode these controls are explicitly not
            # applicable; report them as passed so the UI does not claim that
            # a non-required control is blocking an otherwise ready export.
            "independent_approval": independently_approved or source_first,
            "critical_dq_acknowledged": not unacknowledged or source_first,
            "published": is_published,
            "source_first_mode": source_first,
        },
        "critical_dq_count": len(critical),
        "unacknowledged_critical_count": len(unacknowledged),
        "operational_snapshot_export": {
            "ready": operational_ready,
            "label": "operational/derived",
            "blocking_reasons": blocking_reasons,
        },
        "official_report_export": {
            "ready": False,
            "label": "unavailable",
            "blocking_reasons": [
                workflow_message("official_data_unavailable", language)
            ],
        },
    }


def _published_snapshot_or_error(
    session: Session, snapshot_id: UUID, actor: Actor
) -> PortfolioSnapshotRecord:
    snapshot = _get_snapshot(session, snapshot_id, actor)
    if snapshot.import_batch.status != ImportStatus.PUBLISHED:
        raise HTTPException(
            status_code=409,
            detail="Выгрузка доступна только для опубликованной версии портфеля",
        )
    return snapshot


def _record_snapshot_export(
    session: Session,
    snapshot: PortfolioSnapshotRecord,
    actor: Actor,
    action: str,
    filename: str,
    detail: dict[str, Any],
) -> None:
    session.add(
        AuditEvent(
            import_batch=snapshot.import_batch,
            actor_id=actor.actor_id,
            action=action,
            detail={"format": "xlsx", "filename": filename, **detail},
        )
    )
    session.commit()


def _filter_dq_issues(
    issues: list[dict[str, Any]], term: str, severity: str
) -> list[dict[str, Any]]:
    normalized = term.casefold()
    return [
        issue
        for issue in issues
        if (severity == "all" or issue["severity"] == severity)
        and (
            not normalized
            or any(
                normalized in value.casefold()
                for value in [
                    issue["code"], issue["message"], *issue["affected_fields"]
                ]
            )
        )
    ]


def _get_dq_issue(
    session: Session, issue_id: UUID, actor: Actor
) -> DataQualityIssueRecord:
    try:
        issue = get_dq_issue_or_error(session, issue_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    require_domain(actor, "back_office")
    require_portfolio(actor, issue.snapshot.portfolio_code)
    return issue


def _is_overdue(issue: DataQualityIssueRecord) -> bool:
    # date.today(), not utcnow().date() - see services/multi_source.py's
    # _readiness_status for why (this app runs on a machine configured for
    # the business's own timezone, confirmed UTC+5).
    return bool(issue.owner_id and issue.due_date and issue.due_date < date.today())


def _weighted_average_ytm(ytm_weight_pairs: list[tuple[Decimal, Decimal]]) -> str | None:
    """Combine an instrument's per-lot YTMs into one figure.

    Lots of the same ISIN routinely report slightly different current YTM
    (bought at different times/prices), so this used to only show a value
    when every lot agreed exactly and fall back to "Недоступно" otherwise -
    confirmed against a real OSIP workbook where two lots of the same bond
    differed by ~0.005pp and the instrument row showed nothing at all. A
    carrying-value-weighted average represents the position honestly
    without needing exact agreement; it degrades to a plain average only
    when no lot has a usable carrying value to weight by (never fabricates
    a weight), and is skipped entirely (None) when no lot has a YTM.
    """
    if not ytm_weight_pairs:
        return None
    total_weight = sum(weight for _, weight in ytm_weight_pairs)
    if total_weight > 0:
        weighted_sum = sum(ytm * weight for ytm, weight in ytm_weight_pairs)
        return _decimal(weighted_sum / total_weight)
    return _decimal(sum(ytm for ytm, _ in ytm_weight_pairs) / len(ytm_weight_pairs))


def _aggregated_holdings(snapshot: PortfolioSnapshotRecord, *, include_internal: bool = False) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    dividend_history = load_dividend_history()
    dividend_as_of = date.today()
    for lot in snapshot.position_lots:
        group = groups.setdefault(
            lot.isin,
            {
                "isin": lot.isin,
                "security_code": lot.instrument.security_code,
                "issuer": lot.instrument.issuer,
                "raw_security_type": lot.instrument.raw_security_type,
                "normalized_asset_class": lot.instrument.normalized_asset_class,
                "true_asset_class": true_asset_class(
                    lot.instrument.normalized_asset_class,
                    lot.instrument.raw_security_type,
                    lot.instrument.raw_sector,
                    lot.instrument.security_code,
                    instrument_class(lot.isin),
                ),
                "instrument_currency": lot.instrument.instrument_currency,
                "raw_sector": lot.instrument.raw_sector,
                "lot_count": 0,
                "quantity": Decimal("0"),
                "current_ytms": [],
                "carrying_amount_natives": [],
                "ratings": [],
                "listing_ratings": [],
                "purchase_amount_native": Decimal("0"),
                "purchase_amount_kzt": Decimal("0"),
                "derived_carrying_value_kzt": Decimal("0"),
                # A lot with no source carrying amount (domain.py's
                # derived_carrying_value_kzt returns None for it - e.g. a
                # short-dated deposit the source never marks a current
                # balance for) must not silently count as zero: that
                # quietly excludes real, source-confirmed purchase money
                # from this instrument's total and, worse, from the whole
                # portfolio's derived-basis total/weight below - the
                # weight check then still reads "OK 100%" because it's
                # checking consistency against an already-too-low total,
                # not against reality. Track completeness so an
                # incomplete instrument's total/weight/HPR come out
                # "unavailable" instead of a falsely precise, too-small
                # number - see snapshot_overview's carrying_complete for
                # the same discipline already applied to the KPI card.
                "derived_carrying_complete": True,
                "dividend_income_kzt": Decimal("0"),
                "dividend_income_native": Decimal("0"),
                "dividend_unavailable": False,
                "coupon_income_kzt_estimated": Decimal("0"),
                "coupon_income_native_estimated": Decimal("0"),
                "coupon_estimate_unavailable": False,
                "source_refs": [],
            },
        )
        group["lot_count"] += 1
        group["quantity"] += lot.quantity
        if lot.current_ytm is not None:
            # Weight each lot's YTM by its own carrying value, so a small
            # residual lot doesn't pull the instrument-level figure as far
            # as the lot actually holding most of the position.
            group["current_ytms"].append((lot.current_ytm, lot.derived_carrying_value_kzt or Decimal("0")))
        if lot.carrying_amount_native is not None:
            group["carrying_amount_natives"].append(lot.carrying_amount_native)
        group["ratings"].extend(
            [lot.rating_sp, lot.rating_moodys, lot.rating_fitch]
        )
        if lot.listing_rating:
            group["listing_ratings"].append(lot.listing_rating)
        group["purchase_amount_native"] += lot.purchase_amount_native or Decimal("0")
        group["purchase_amount_kzt"] += lot.purchase_amount_kzt or Decimal("0")
        if lot.derived_carrying_value_kzt is None:
            group["derived_carrying_complete"] = False
        else:
            group["derived_carrying_value_kzt"] += lot.derived_carrying_value_kzt
        dividend = lot_dividend_contribution(
            lot, history=dividend_history, current_date=dividend_as_of
        )
        if dividend.kzt_amount is not None:
            group["dividend_income_kzt"] += dividend.kzt_amount
        elif dividend.unavailable:
            group["dividend_unavailable"] = True
        if dividend.matched_count:
            group["dividend_income_native"] += dividend.native_amount
        if is_coupon_bearing_lot(lot):
            coupon_native = estimated_paid_coupon_income_native(lot, snapshot.report_date)
            coupon_kzt = estimated_coupon_income_kzt(lot, coupon_native)
            if coupon_native is None or coupon_kzt is None:
                group["coupon_estimate_unavailable"] = True
            else:
                group["coupon_income_native_estimated"] += coupon_native
                group["coupon_income_kzt_estimated"] += coupon_kzt
        group["source_refs"].append(
            _source_payload(lot.source_row, snapshot.import_batch)
        )
    # Incomplete instruments are excluded from the derived-basis total/weight
    # denominator, not counted in it as zero - otherwise the weight-validation
    # check below would still read "OK 100%" while silently checking
    # consistency against an already-too-small total.
    derived_total = sum(
        (
            group["derived_carrying_value_kzt"]
            for group in groups.values()
            if group["derived_carrying_complete"]
        ),
        Decimal("0"),
    )
    purchase_total = sum(
        (group["purchase_amount_kzt"] for group in groups.values()), Decimal("0")
    )
    items = []
    for group in groups.values():
        derived_complete = group["derived_carrying_complete"]
        derived_value = group["derived_carrying_value_kzt"] if derived_complete else None
        items.append({
            **{
                key: value
                for key, value in group.items()
                if key
                not in {
                    "quantity",
                    "current_ytms",
                    "carrying_amount_natives",
                    "ratings",
                    "listing_ratings",
                    "purchase_amount_native",
                    "purchase_amount_kzt",
                    "derived_carrying_value_kzt",
                    "derived_carrying_complete",
                    "dividend_income_kzt",
                    "dividend_income_native",
                    "dividend_unavailable",
                    "coupon_income_kzt_estimated",
                    "coupon_income_native_estimated",
                    "coupon_estimate_unavailable",
                }
            },
            "quantity": _decimal(group["quantity"]),
            "hpr_percent": _decimal(
                hpr_percent(
                    group["purchase_amount_kzt"],
                    derived_value,
                    (
                        None
                        if group["dividend_unavailable"]
                        else group["dividend_income_kzt"] + group["coupon_income_kzt_estimated"]
                    ),
                )
            ),
            "dividend_income_native": _decimal(group["dividend_income_native"]),
            "dividend_income_kzt": _decimal(group["dividend_income_kzt"]),
            "dividend_unavailable": group["dividend_unavailable"],
            "coupon_income_native_estimated": _decimal(group["coupon_income_native_estimated"]),
            "coupon_income_kzt_estimated": _decimal(group["coupon_income_kzt_estimated"]),
            "coupon_estimate_unavailable": group["coupon_estimate_unavailable"],
            "current_ytm": _weighted_average_ytm(group["current_ytms"]),
            "carrying_amount_native": _decimal(
                sum(group["carrying_amount_natives"], Decimal("0"))
            )
            if len(group["carrying_amount_natives"]) == group["lot_count"]
            else None,
            "rating_sp": next(
                (value for value in group["ratings"][0::3] if value), ""
            ),
            "rating_moodys": next(
                (value for value in group["ratings"][1::3] if value), ""
            ),
            "rating_fitch": next(
                (value for value in group["ratings"][2::3] if value), ""
            ),
            "listing_rating": next(iter(group["listing_ratings"]), ""),
            "purchase_amount_native": _decimal(group["purchase_amount_native"]),
            "purchase_amount_kzt": _decimal(group["purchase_amount_kzt"]),
            "derived_carrying_value_kzt": _decimal(derived_value),
            "derived_carrying_incomplete": not derived_complete,
            "derived_weight_percent": (
                _percentage(derived_value, derived_total) if derived_complete else None
            ),
            "purchase_weight_percent": _percentage(
                group["purchase_amount_kzt"], purchase_total
            ),
        })
    items.sort(
        key=lambda item: Decimal(item["derived_carrying_value_kzt"] or "0"),
        reverse=True,
    )
    if not include_internal:
        for item in items:
            item.pop("dividend_income_native", None)
            item.pop("dividend_income_kzt", None)
            item.pop("dividend_unavailable", None)
    return items


def _filter_instrument_holdings(
    items: list[dict[str, Any]], *, term: str, asset_class: str | None
) -> list[dict[str, Any]]:
    normalized_term = term.casefold()
    return [
        item
        for item in items
        if (
            not asset_class
            or item["normalized_asset_class"] == asset_class
            or item.get("true_asset_class") == asset_class
        )
        and (
            not normalized_term
            or any(
                normalized_term in value.casefold()
                for value in (item["isin"], item["security_code"], item["issuer"])
            )
        )
    ]


def _allocation_label(lot, dimension: str) -> str:
    if dimension == "asset_class":
        return lot.instrument.normalized_asset_class
    if dimension == "currency":
        return lot.instrument_currency or "Not supplied"
    if dimension == "issuer":
        return lot.issuer or "Not supplied"
    if dimension == "valuation_method":
        return lot.valuation_method or "Not supplied"
    if dimension == "raw_sector":
        return lot.raw_sector or "Not supplied"
    return lot.rating_sp or lot.rating_moodys or lot.rating_fitch or "Not supplied"


def _percentage(value: Decimal, total: Decimal) -> str:
    if total == 0:
        return "0"
    return _decimal(value * Decimal("100") / total) or "0"


def _source_payload(
    source_row,
    batch: ImportBatch,
    field: str | None = None,
    value: Any = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Serialize a source row and, when known, its physical Excel location."""
    reference: dict[str, Any] = {
        "workbook_name": source_row.workbook_name,
        "sheet_name": source_row.sheet_name,
        "row_number": source_row.row_number,
        "parser_version": source_row.parser_version,
        "source_row_id": str(source_row.id),
        "source_kind": "row",
    }
    if field:
        reference["field"] = field
        reference["value"] = _decimal(value) if isinstance(value, Decimal) else (str(value) if value is not None else None)
        column = _osip_source_column(field, source_row.sheet_name, batch)
        if column is not None:
            letter = _excel_column_letter(column)
            reference.update({
                "source_column": column,
                "source_column_letter": letter,
                "source_cell": f"{letter}{source_row.row_number}",
            })
    if note:
        reference["note"] = note
    return reference


def _metric(value: Any, basis: str) -> dict[str, Any]:
    return {
        "value": _decimal(value) if isinstance(value, Decimal) else value,
        "basis": basis,
    }
