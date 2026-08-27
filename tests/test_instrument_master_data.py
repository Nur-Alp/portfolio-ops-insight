"""Instrument reference data (issuer/sector/asset class) must track the most
recently persisted snapshot for a given ISIN, not freeze at first sight."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from osip_dashboard.domain import PortfolioSnapshot, PositionLotSnapshot, SourceRef
from osip_dashboard.persistence.models import ImportBatch, ImportStatus, InstrumentRecord
from osip_dashboard.services.imports import _persist_snapshot, ensure_reference_data, ensure_portfolio


def _position(*, isin: str, raw_security_type: str, issuer: str, source_section: str, quantity: Decimal = Decimal("1"), carrying_amount_native: Decimal | None = None, carrying_price_native: Decimal | None = None) -> PositionLotSnapshot:
    return PositionLotSnapshot(
        portfolio_code="SOBSTV",
        report_date=date(2026, 7, 15),
        source=SourceRef("test.xls", "ОСИП_ПОРТФЕЛЬ", 10),
        source_section=source_section,
        security_code="TEST1",
        isin=isin,
        raw_security_type=raw_security_type,
        issuer=issuer,
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
        quantity=quantity,
        purchase_date=None,
        purchase_price=None,
        purchase_yield=None,
        current_ytm=None,
        purchase_amount_native=Decimal("100"),
        purchase_amount_kzt=Decimal("100"),
        carrying_amount_native=carrying_amount_native,
        carrying_price_native=carrying_price_native,
        reserve_kzt=None,
        organizer_fee_kzt=None,
        broker_fee_kzt=None,
        accrued_income_kzt=None,
        principal_indexation=None,
        report_fx_rate=None,
        next_coupon_date=None,
        previous_coupon_date=None,
        listing_rating="",
    )


def test_source_carrying_price_is_preserved_without_rescaling():
    position = _position(
        isin="PRICE-1", raw_security_type="Облигация", issuer="Issuer", source_section="Облигации",
        quantity=Decimal("3"), carrying_amount_native=Decimal("2910.4567"), carrying_price_native=Decimal("97.0100"),
    )
    assert position.carrying_price_native == Decimal("97.0100")


def _snapshot(position: PositionLotSnapshot) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        portfolio_code="SOBSTV",
        report_date=position.report_date,
        source_path=Path("test.xls"),
        source_sha256="0" * 64,
        positions=(position,),
        raw_settlements=(),
        settlements=(),
        cash_balances=(),
        issues=(),
    )


def test_instrument_record_refreshes_on_corrected_reimport(api):
    with api.app.state.session_factory() as session:
        ensure_reference_data(session)
        ensure_portfolio(session, portfolio_code="SOBSTV", portfolio_name=None)

        first_batch = ImportBatch(
            portfolio_code="SOBSTV",
            source_sha256="1" * 64,
            original_filename="first.xls",
            storage_key="1" * 64,
            parser_version="test",
            status=ImportStatus.VALIDATING,
            uploader_id="uploader-1",
        )
        session.add(first_batch)
        session.flush()
        _persist_snapshot(
            session,
            first_batch,
            _snapshot(
                _position(
                    isin="KZ000000TEST",
                    raw_security_type="Акция",
                    issuer="Old Issuer Name Ltd",
                    source_section="Акции",
                )
            ),
        )
        session.commit()

        instrument = session.get(InstrumentRecord, "KZ000000TEST")
        assert instrument.issuer == "Old Issuer Name Ltd"
        assert instrument.normalized_asset_class == "Equity"

        second_batch = ImportBatch(
            portfolio_code="SOBSTV",
            source_sha256="2" * 64,
            original_filename="corrected.xls",
            storage_key="2" * 64,
            parser_version="test",
            status=ImportStatus.VALIDATING,
            uploader_id="uploader-1",
        )
        session.add(second_batch)
        session.flush()
        _persist_snapshot(
            session,
            second_batch,
            _snapshot(
                _position(
                    isin="KZ000000TEST",
                    raw_security_type="РЕПО",
                    issuer="Corrected Issuer Name JSC",
                    source_section="РЕПО",
                )
            ),
        )
        session.commit()

        instrument = session.get(InstrumentRecord, "KZ000000TEST")
        assert instrument.issuer == "Corrected Issuer Name JSC"
        assert instrument.normalized_asset_class == "Repo"
