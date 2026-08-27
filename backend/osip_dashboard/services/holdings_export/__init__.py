"""Restrained, source-traceable Excel exports for published OSIP data.

This package is split by concern rather than by business domain:

- ``shared``: generic Excel-writing helpers used across every export type.
- ``coupons``: coupon/dividend income calculation helpers (pure calculation,
  some also imported directly by ``api_handlers.py``).
- ``distribution``: currency / true-class / risk / factor distribution
  sheets and their supporting USD/rating helpers.
- ``holdings``: the holdings, position-lots, expected-cash-flows and
  source-lots exports.
- ``other_exports``: cash calendar, data-quality issues and import-registry
  exports.

This module re-exports everything that is imported from elsewhere (either
``api_handlers.py`` or the test suite) so those call sites keep working
unchanged.
"""

from __future__ import annotations

from osip_dashboard.services.holdings_export.coupons import (
    _accrued_or_dividend_kzt,
    _coupon_accrued_kzt,
    _coupon_or_dividend_native,
    _derive_expected_coupon_native,
    _dividend_freshness_note,
    estimated_coupon_income_kzt,
    estimated_coupon_income_native,
    estimated_paid_coupon_income_native,
    expected_coupon_native,
    is_coupon_bearing_lot,
    lot_maturity_amount_native,
)
from osip_dashboard.services.holdings_export.distribution import (
    _hpr_usd_percent_for_item,
    _instrument_focus,
    _risk_bucket,
    _write_distribution_block,
)
from osip_dashboard.services.holdings_export.holdings import (
    _append_control_sheet,
    _expected_cash_flow_rows,
    create_holdings_xlsx,
    create_lots_xlsx,
)
from osip_dashboard.services.holdings_export.other_exports import (
    create_cash_calendar_xlsx,
    create_dq_issues_xlsx,
    create_import_registry_xlsx,
)

__all__ = [
    "_accrued_or_dividend_kzt",
    "_append_control_sheet",
    "_coupon_accrued_kzt",
    "_coupon_or_dividend_native",
    "_derive_expected_coupon_native",
    "_dividend_freshness_note",
    "_expected_cash_flow_rows",
    "_hpr_usd_percent_for_item",
    "_instrument_focus",
    "_risk_bucket",
    "_write_distribution_block",
    "create_cash_calendar_xlsx",
    "create_dq_issues_xlsx",
    "create_holdings_xlsx",
    "create_import_registry_xlsx",
    "create_lots_xlsx",
    "estimated_coupon_income_kzt",
    "estimated_coupon_income_native",
    "estimated_paid_coupon_income_native",
    "expected_coupon_native",
    "is_coupon_bearing_lot",
    "lot_maturity_amount_native",
]
