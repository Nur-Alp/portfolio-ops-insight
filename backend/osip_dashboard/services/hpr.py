"""Shared HPR arithmetic used by API and workbook exports."""

from __future__ import annotations

from datetime import date
from decimal import Decimal


def hpr_amount(
    purchase_amount: Decimal | None,
    carrying_amount: Decimal | None,
    dividend_amount: Decimal | None = Decimal("0"),
) -> Decimal | None:
    """Return holding-period return amount, or unavailable when inputs are incomplete."""
    if purchase_amount in (None, Decimal("0")) or carrying_amount is None or dividend_amount is None:
        return None
    return carrying_amount - purchase_amount + dividend_amount


def hpr_percent(
    purchase_amount: Decimal | None,
    carrying_amount: Decimal | None,
    dividend_amount: Decimal | None = Decimal("0"),
) -> Decimal | None:
    """Return HPR as percentage points (``16.7`` means 16.7%), not an Excel fraction."""
    amount = hpr_amount(purchase_amount, carrying_amount, dividend_amount)
    if amount is None or purchase_amount in (None, Decimal("0")):
        return None
    return amount * Decimal("100") / purchase_amount


def estimated_coupon_income(
    nominal: Decimal | None,
    quantity: Decimal | None,
    coupon_rate: Decimal | None,
    purchase_date: date | None,
    report_date: date | None,
    *,
    day_count: Decimal = Decimal("360"),
) -> Decimal | None:
    """Estimate gross coupon income over a lot's holding period.

    OSIP does not provide a paid-coupon ledger.  This deliberately simple
    estimate uses the requested ``nominal × quantity × rate × days / 360``
    convention.  It is an income estimate, not evidence of an actual payment
    and must not be combined with future/expected coupons.
    """
    if (
        nominal is None
        or quantity is None
        or coupon_rate is None
        or purchase_date is None
        or report_date is None
        or day_count <= 0
    ):
        return None
    holding_days = max((report_date - purchase_date).days, 0)
    return nominal * quantity * coupon_rate * Decimal(holding_days) / day_count
