"""Coupon and dividend income calculation helpers for OSIP exports.

These are pure-calculation functions (no Excel writing). Several are also
imported directly by ``api_handlers.py``, not just used internally here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from osip_dashboard.services.hpr import estimated_coupon_income
from osip_dashboard.services.holdings_export.shared import _decimal_value, _optional_decimal


def _dividend_freshness_note(status: Any) -> str:
    if status.future_pay_count % 10 == 1 and status.future_pay_count % 100 != 11:
        future_label = "будущая выплата"
    elif status.future_pay_count % 10 in {2, 3, 4} and status.future_pay_count % 100 not in {12, 13, 14}:
        future_label = "будущие выплаты"
    else:
        future_label = "будущих выплат"
    future_note = (
        f" В книге есть {status.future_pay_count} {future_label}; они не включены в HPR до наступления pay-date."
        if status.future_pay_count
        else ""
    )
    if status.freshness == "fresh":
        source_date = status.source_date.strftime("%d.%m.%Y") if status.source_date else "дата не указана"
        return f"Данные о дивидендах Bloomberg актуальны на {source_date} (порог устаревания — {status.stale_after_days} дней).{future_note}"
    if status.freshness == "stale":
        source_date = status.source_date.strftime("%d.%m.%Y") if status.source_date else "дата не указана"
        return f"ВНИМАНИЕ: данные о дивидендах Bloomberg устарели: последняя дата выгрузки {source_date}; HPR может быть занижен из-за пропущенных выплат.{future_note}"
    if status.freshness == "unknown":
        return f"ВНИМАНИЕ: дата выгрузки данных о дивидендах Bloomberg не подтверждена; дивидендная часть HPR имеет неопределённую полноту.{future_note}"
    return f"ВНИМАНИЕ: данные о дивидендах Bloomberg отсутствуют; HPR рассчитан без дивидендной корректировки.{future_note}"


def _coupon_accrued_kzt(lot: Any) -> Decimal | str:
    """Return only accumulated coupon interest from the OSIP source.

    The source's accumulated-coupon field is resolved by header label and is
    already expressed in KZT for the bond rows. This export excludes
    dividends, repo remuneration, deposit interest and the separate expected
    coupon field.
    """
    security_type = str(getattr(lot, "raw_security_type", "") or "").casefold()
    if not any(token in security_type for token in ("облигац", "гцб", "bond")):
        return "Недоступно"
    return _optional_decimal(getattr(lot, "accrued_income_kzt", None))


def _accrued_or_dividend_kzt(lot: Any, dividend: Any) -> Decimal | str:
    """Show KZT accrued income for coupons and validated paid dividends.

    OSIP's accrued-income field remains the source coupon component. Dividend
    history is additive and only contributes when the lot passed the strict
    ex-date/pay-date test and has a KZT conversion. If neither component is
    available, keep the explicit ``Недоступно`` value.
    """
    components: list[Decimal] = []
    accrued = _coupon_accrued_kzt(lot)
    if isinstance(accrued, Decimal):
        components.append(accrued)
    if getattr(dividend, "matched_count", 0):
        dividend_kzt = getattr(dividend, "kzt_amount", None)
        if dividend_kzt is not None:
            components.append(_decimal_value(dividend_kzt))
    return sum(components, Decimal("0")) if components else "Недоступно"


def _coupon_or_dividend_native(coupon_native: Decimal | None, dividend: Any) -> Decimal | str:
    """Combine estimated paid coupon and validated dividend in price currency."""
    components: list[Decimal] = []
    if coupon_native is not None:
        components.append(coupon_native)
    if getattr(dividend, "matched_count", 0):
        components.append(_decimal_value(getattr(dividend, "native_amount", Decimal("0"))))
    return sum(components, Decimal("0")) if components else "Недоступно"


def is_coupon_bearing_lot(lot: Any) -> bool:
    """Return whether the lot has a bond coupon rather than a repo rate."""
    security_type = str(getattr(lot, "raw_security_type", "") or "").casefold()
    if any(token in security_type for token in ("репо", "repo")):
        return False
    return any(token in security_type for token in ("облигац", "гцб", "bond"))


def estimated_coupon_income_native(lot: Any, report_date: date) -> Decimal | None:
    """Estimate gross coupon income in the lot's native currency.

    This is intentionally separate from ``accrued_income_kzt``: the latter is
    the current unpaid accrual already included in carrying value, while this
    estimate approximates income earned during the whole holding period.
    """
    if not is_coupon_bearing_lot(lot):
        return None
    return estimated_coupon_income(
        getattr(lot, "nominal_value", None),
        getattr(lot, "quantity", None),
        getattr(lot, "coupon_or_repo_rate", None),
        getattr(lot, "purchase_date", None),
        report_date,
    )


def estimated_paid_coupon_income_native(lot: Any, report_date: date) -> Decimal | None:
    """Estimate coupon income to add to HPR without double-counting accrual.

    The gross 360-day estimate includes the current coupon period. OSIP's
    derived carrying value already adds the current unpaid accrued coupon, so
    only the estimated amount above that accrual is added to HPR. This remains
    an approximation, not a payment ledger.
    """
    gross = estimated_coupon_income_native(lot, report_date)
    if gross is None:
        return None
    accrued_kzt = getattr(lot, "accrued_income_kzt", None)
    if accrued_kzt is None:
        return gross
    currency = str(getattr(lot, "instrument_currency", "") or "").upper()
    if currency == "KZT":
        accrued_native = _decimal_value(accrued_kzt)
    elif currency == "USD" and getattr(lot, "report_fx_rate", None):
        accrued_native = _decimal_value(accrued_kzt) / _decimal_value(lot.report_fx_rate)
    else:
        return None
    previous_coupon_date = getattr(lot, "previous_coupon_date", None)
    purchase_date = getattr(lot, "purchase_date", None)
    if (
        previous_coupon_date
        and purchase_date
        and previous_coupon_date < report_date
        and purchase_date > previous_coupon_date
    ):
        accrual_days = (report_date - previous_coupon_date).days
        holding_accrual_days = (report_date - purchase_date).days
        if accrual_days > 0:
            accrued_native *= Decimal(max(holding_accrual_days, 0)) / Decimal(accrual_days)
    return max(gross - accrued_native, Decimal("0"))


def estimated_coupon_income_kzt(lot: Any, coupon_native: Decimal | None) -> Decimal | None:
    """Convert the estimated native coupon to KZT for KZT HPR."""
    if coupon_native is None:
        return None
    currency = str(getattr(lot, "instrument_currency", "") or "").upper()
    if currency == "KZT":
        return coupon_native
    if currency == "USD" and getattr(lot, "report_fx_rate", None):
        return coupon_native * _decimal_value(lot.report_fx_rate)
    return None


def lot_maturity_amount_native(lot: Any) -> Decimal | None:
    """Nominal x quantity - the redemption/repo-close amount, in the lot's own currency.

    Shared by the Expected Cash Flows sheet and the cash-calendar view/export
    (``snapshot_calendar`` in ``api_handlers.py``) so both agree on the same
    event's amount instead of one silently leaving it "Недоступно" while the
    other computes it.
    """
    if lot.nominal_value is None or lot.quantity is None:
        return None
    return _decimal_value(lot.nominal_value) * _decimal_value(lot.quantity)


def expected_coupon_native(lot: Any) -> Decimal | None:
    """Read the source workbook's expected-coupon cell without recalculating it.

    ``expected_coupon_cached`` is resolved at parse time by header label
    (``Сумма ожидаемого купона``, see ``_FIELD_LABELS`` in
    ``ingestion/osip_workbook.py``), not a fixed column index - the OSIP
    generator has moved this column before (five rating columns inserted
    ahead of it), and a raw positional read broke silently for exactly that
    reason (misread as a large KZT-scale value while still labeled in the
    lot's own USD currency).

    This column is a live Excel formula in the OSIP generator that is saved
    with an invalid/blank cached result (see ``BROKEN_CALCULATED_FIELDS`` in
    ``ingestion/osip_workbook.py``) - Excel recomputes it on open, but the
    parser only ever sees the broken cache. When the cell is blank for that
    reason, fall back to deriving the amount ourselves instead of leaving a
    real, calculable figure as unavailable.
    """
    if getattr(lot, "next_coupon_date", None) is None:
        return None
    cached = getattr(lot, "expected_coupon_cached", None)
    if cached is not None:
        return cached
    return _derive_expected_coupon_native(lot)


def _derive_expected_coupon_native(lot: Any) -> Decimal | None:
    """Derive the expected coupon when OSIP's own formula cache is blank.

    nominal x rate / frequency x quantity, where frequency (payments per
    year - 1 annual, 2 semi-annual, 4 quarterly, ...) is inferred from the
    coupon period length as ``round(365 / period_days)``. A bond's coupon
    payment is a fixed fraction of the annual rate per the payment
    schedule, not a pro-rata slice of the exact calendar days between two
    coupon dates (those vary by a few days depending on month lengths, but
    the payment itself doesn't). Verified against a real OSIP workbook by
    recalculating it with LibreOffice (which evaluates OSIP's actual
    formula, cache bug and all): an earlier actual/365-of-period-days
    version of this function matched a plain annual bond exactly but was
    consistently ~0.3-0.8% off on semi-annual/quarterly ones; this
    frequency-based version reproduced all 7 tested lots (annual, semi-annual,
    and quarterly) exactly.

    Requires both the previous and next coupon dates to establish the
    period length; a first coupon with no prior date is left unavailable
    rather than guessing a period length. This is a computed stand-in for
    the source's own formula, not a source read - callers/sheets that show
    it disclose as much.
    """
    rate = getattr(lot, "coupon_or_repo_rate", None)
    nominal = getattr(lot, "nominal_value", None)
    quantity = getattr(lot, "quantity", None)
    previous_date = getattr(lot, "previous_coupon_date", None)
    next_date = getattr(lot, "next_coupon_date", None)
    if rate is None or nominal is None or quantity is None or previous_date is None or next_date is None:
        return None
    period_days = (next_date - previous_date).days
    if period_days <= 0:
        return None
    frequency = max(1, round(Decimal(365) / Decimal(period_days)))
    return _decimal_value(nominal) * _decimal_value(rate) / Decimal(frequency) * _decimal_value(quantity)
