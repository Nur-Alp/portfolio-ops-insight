from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path
from types import SimpleNamespace


_SPEC = importlib.util.spec_from_file_location(
    "audit_hpr_export", Path(__file__).parents[1] / "scripts" / "audit_hpr_export.py"
)
assert _SPEC and _SPEC.loader
_AUDIT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_AUDIT)
_estimated_hpr_income = _AUDIT._estimated_hpr_income


def test_hpr_audit_income_matches_coupon_plus_dividend_export_logic():
    lot = SimpleNamespace(
        raw_security_type="Корпоративные облигации",
        instrument_currency="KZT",
        nominal_value=Decimal("1000"),
        quantity=Decimal("10"),
        coupon_or_repo_rate=Decimal("0.12"),
        purchase_date=date(2026, 1, 1),
        accrued_income_kzt=None,
        previous_coupon_date=None,
        report_fx_rate=Decimal("500"),
    )
    contribution = SimpleNamespace(
        matched_count=1,
        kzt_amount=Decimal("15"),
        native_amount=Decimal("10"),
    )

    kzt_income, usd_income = _estimated_hpr_income(
        lot, contribution, report_date=date(2026, 7, 1), usd_rate=Decimal("500")
    )

    # 603.333... estimated paid coupon + 15 validated dividend, with the
    # same KZT/USD conversion used by the holdings export.
    assert kzt_income == Decimal("618.3333333333333333333333333")
    assert usd_income == Decimal("1.236666666666666666666666667")
