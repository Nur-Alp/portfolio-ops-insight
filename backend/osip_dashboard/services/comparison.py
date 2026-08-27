"""Stable import preview and prior-approved snapshot comparison."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from osip_dashboard.persistence.models import ImportBatch, ImportStatus, PositionLotRecord


COMPARABLE_STATUSES = (
    ImportStatus.APPROVED,
    ImportStatus.PUBLISHED,
    ImportStatus.SUPERSEDED,
)


def compare_import_to_prior_approved(
    session: Session, current: ImportBatch
) -> dict[str, Any]:
    if current.snapshot is None or current.report_date is None or current.version is None:
        raise ValueError("Для предварительного просмотра у загрузки нет проверенного снимка")

    baseline = session.scalar(
        select(ImportBatch)
        .where(
            ImportBatch.portfolio_code == current.portfolio_code,
            ImportBatch.id != current.id,
            ImportBatch.status.in_(COMPARABLE_STATUSES),
            ImportBatch.report_date.is_not(None),
            or_(
                ImportBatch.report_date < current.report_date,
                and_(
                    ImportBatch.report_date == current.report_date,
                    ImportBatch.version < current.version,
                ),
            ),
        )
        .order_by(ImportBatch.report_date.desc(), ImportBatch.version.desc())
        .limit(1)
    )
    current_snapshot = current.snapshot
    baseline_snapshot = baseline.snapshot if baseline else None
    metric_definitions = (
        ("position_count", "source"),
        ("unique_isin_count", "source"),
        ("raw_settlement_count", "source"),
        ("settlement_count", "derived"),
        ("purchase_amount_kzt", "source"),
        ("derived_carrying_value_kzt", "derived"),
        ("cash_kzt", "source"),
        ("derived_operational_total_kzt", "derived"),
        ("total_fees_kzt", "source"),
        ("total_reserves_kzt", "source"),
    )
    metrics: dict[str, dict[str, Any]] = {}
    for name, basis in metric_definitions:
        current_value = getattr(current_snapshot, name)
        baseline_value = getattr(baseline_snapshot, name) if baseline_snapshot else None
        metrics[name] = {
            "current": current_value,
            "baseline": baseline_value,
            "delta": current_value - baseline_value
            if baseline_value is not None
            else None,
            "basis": basis,
        }

    current_lots = _lot_counter(current_snapshot.position_lots)
    baseline_lots = _lot_counter(baseline_snapshot.position_lots) if baseline_snapshot else Counter()
    added = current_lots - baseline_lots
    removed = baseline_lots - current_lots
    unchanged = current_lots & baseline_lots
    return {
        "current": current,
        "baseline": baseline,
        "metrics": metrics,
        "lot_changes": {
            "added_count": sum(added.values()),
            "removed_count": sum(removed.values()),
            "unchanged_count": sum(unchanged.values()),
            "added": _expanded_lots(added),
            "removed": _expanded_lots(removed),
        },
    }


def _lot_counter(lots: list[PositionLotRecord]) -> Counter[tuple[str, ...]]:
    return Counter(_lot_signature(lot) for lot in lots)


def _lot_signature(lot: PositionLotRecord) -> tuple[str, ...]:
    return (
        lot.isin,
        lot.security_code,
        lot.purchase_date.isoformat() if lot.purchase_date else "",
        _canonical_decimal(lot.quantity),
        _canonical_decimal(lot.purchase_price),
        lot.instrument_currency,
    )


def _expanded_lots(counter: Counter[tuple[str, ...]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for signature, count in sorted(counter.items()):
        isin, security_code, purchase_date, quantity, purchase_price, currency = signature
        items.append(
            {
                "isin": isin,
                "security_code": security_code,
                "purchase_date": purchase_date or None,
                "quantity": quantity,
                "purchase_price": purchase_price or None,
                "instrument_currency": currency,
                "lot_count": count,
            }
        )
    return items


def _canonical_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
