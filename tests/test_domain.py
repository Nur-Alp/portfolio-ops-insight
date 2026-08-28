"""Unit tests for the canonical PositionLotSnapshot derivations in domain.py."""

from datetime import date
from decimal import Decimal

from osip_dashboard.domain import PositionLotSnapshot, SourceRef


def _position(*, raw_security_type: str, source_section: str = "", accrued_income_kzt: Decimal | None = None) -> PositionLotSnapshot:
    return PositionLotSnapshot(
        portfolio_code="SOBSTV",
        report_date=date(2026, 7, 15),
        source=SourceRef("test.xls", "ОСИП_ПОРТФЕЛЬ", 10),
        source_section=source_section,
        security_code="TEST1",
        isin="TEST-ISIN",
        raw_security_type=raw_security_type,
        issuer="Test Issuer",
        valuation_method="",
        instrument_currency="KZT",
        raw_sector="Corporate",
        rating_sp="",
        rating_moodys="",
        rating_fitch="",
        coupon_or_repo_rate=None,
        nominal_value=None,
        open_date=None,
        close_date=None,
        quantity=Decimal("1"),
        purchase_date=None,
        purchase_price=None,
        purchase_yield=None,
        current_ytm=None,
        purchase_amount_native=Decimal("100"),
        purchase_amount_kzt=Decimal("100"),
        carrying_amount_native=Decimal("100"),
        carrying_price_native=None,
        reserve_kzt=None,
        organizer_fee_kzt=None,
        broker_fee_kzt=None,
        accrued_income_kzt=accrued_income_kzt,
        principal_indexation=None,
        report_fx_rate=Decimal("1"),
        next_coupon_date=None,
        previous_coupon_date=None,
        listing_rating="",
    )


def test_derived_carrying_value_adds_accrued_income_for_a_bond():
    bond = _position(raw_security_type="облигация", accrued_income_kzt=Decimal("5"))
    assert bond.derived_carrying_value_kzt == Decimal("105")


def test_derived_carrying_value_excludes_accrued_income_for_a_repo():
    # OSIP's own "Рыночная стоимость" formula only adds accrued interest for
    # a bond/deposit (=AG+AX) - a repo's branch is =AG alone (confirmed via
    # LibreOffice recalculation of a real workbook). Every real repo lot
    # seen so far has accrued_income_kzt blank/zero, so this has never
    # produced an observed divergence - this test locks in the correct
    # behavior for the day one does carry a nonzero accrued figure.
    #
    # Matched on raw_security_type alone, not source_section: every real
    # repo lot checked carries "репо" directly in its own type text
    # ("авторепо"), and source_section is only meaningful when rows are
    # read in their real top-to-bottom order (it's assigned by walking
    # section-header rows sequentially) - a reordered-rows regression test
    # elsewhere confirmed that checking source_section too made this
    # fragile to row order in a way the type field alone isn't.
    repo = _position(raw_security_type="авторепо", accrued_income_kzt=Decimal("5"))
    assert repo.derived_carrying_value_kzt == Decimal("100")


def test_derived_carrying_value_treats_missing_accrued_income_as_zero():
    bond = _position(raw_security_type="облигация", accrued_income_kzt=None)
    assert bond.derived_carrying_value_kzt == Decimal("100")
