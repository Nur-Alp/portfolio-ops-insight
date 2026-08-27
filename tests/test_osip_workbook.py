from datetime import date
from decimal import Decimal
import json
from pathlib import Path

import pytest
from python_calamine import CalamineWorkbook

from osip_dashboard.ingestion import parse_osip_workbook
from osip_dashboard.ingestion.osip_workbook import (
    OsipWorkbookError,
    SHEET_NAME,
    _find_header_row,
    _find_report_date,
    _formula_carrying_price,
    _formula_cells,
    _parse_rows,
    _resolve_columns,
)


WORKBOOK_DIR = Path(__file__).resolve().parents[1] / "Portfolio operations"
MONEY = Decimal("0.01")

# Real OSIP portfolio workbooks are never committed to this repo (see
# tests/conftest.py's workbook_paths fixture) - every test in this file
# parses one directly rather than through that fixture, so skip the whole
# module up front rather than letting each one crash on a StopIteration.
if not any(WORKBOOK_DIR.glob("*.xls")):
    pytest.skip("No local OSIP portfolio workbook - see tests/conftest.py's workbook_paths fixture", allow_module_level=True)


@pytest.fixture(scope="module")
def snapshots():
    parsed = {}
    for path in WORKBOOK_DIR.glob("*.xls"):
        portfolio_code = "SOBSTV" if "СОБСТВ" in path.name.upper() else "TABYS"
        snapshot = parse_osip_workbook(path, portfolio_code=portfolio_code)
        parsed[portfolio_code] = snapshot
    return parsed


def test_both_portfolios_are_discovered(snapshots):
    assert set(snapshots) == {"SOBSTV", "TABYS"}
    assert {snapshot.report_date.isoformat() for snapshot in snapshots.values()} == {"2026-07-15"}


@pytest.mark.parametrize(
    ("portfolio", "lots", "isins", "purchase", "carrying", "cash", "operational"),
    [
        (
            "SOBSTV",
            19,
            15,
            "4695258648.74",
            "4774363156.14",
            "42009877.85",
            "4816373033.99",
        ),
        (
            "TABYS",
            15,
            12,
            "52103596.35",
            "63779568.02",
            "416640.61",
            "64196208.63",
        ),
    ],
)
def test_golden_snapshot_totals(
    snapshots, portfolio, lots, isins, purchase, carrying, cash, operational
):
    snapshot = snapshots[portfolio]
    assert len(snapshot.positions) == lots
    assert len(snapshot.unique_isins) == isins
    assert snapshot.purchase_amount_kzt.quantize(MONEY) == Decimal(purchase)
    assert snapshot.derived_carrying_value_kzt.quantize(MONEY) == Decimal(carrying)
    assert snapshot.cash_kzt.quantize(MONEY) == Decimal(cash)
    assert snapshot.derived_operational_total_kzt.quantize(MONEY) == Decimal(operational)


def test_cross_portfolio_instrument_union_and_lot_preservation(snapshots):
    all_isins = snapshots["SOBSTV"].unique_isins | snapshots["TABYS"].unique_isins
    assert len(all_isins) == 24
    assert sum(position.isin == "US78464A6644" for position in snapshots["TABYS"].positions) == 3
    assert sum(position.isin == "KZKD00001210" for position in snapshots["SOBSTV"].positions) == 2


def test_future_settlements_section_is_excluded(snapshots):
    sobstv = snapshots["SOBSTV"]
    assert not sobstv.raw_settlements
    assert not sobstv.settlements
    assert "DQ-02" not in {issue.code for issue in sobstv.issues}
    assert "DQ-03" not in {issue.code for issue in sobstv.issues}


def test_cash_rows_and_active_balances_are_preserved(snapshots):
    assert len(snapshots["SOBSTV"].cash_balances) == 11
    assert sum(balance.is_active for balance in snapshots["SOBSTV"].cash_balances) == 5
    assert len(snapshots["TABYS"].cash_balances) == 3
    assert sum(balance.is_active for balance in snapshots["TABYS"].cash_balances) == 2


def test_formula_backed_workbook_outputs_do_not_create_false_dq01(snapshots):
    for snapshot in snapshots.values():
        for position in snapshot.positions:
            assert not position.unavailable_fields
        assert "DQ-01" not in {issue.code for issue in snapshot.issues}


def test_formula_backed_balance_price_is_not_exported_as_unavailable(snapshots):
    """Excel-recalculated balance prices must survive the .xls parser."""
    for snapshot in snapshots.values():
        assert snapshot.positions
        assert all(position.carrying_price_native is not None for position in snapshot.positions)


def test_legacy_formula_cells_are_detected_in_each_workbook():
    for path in WORKBOOK_DIR.glob("*.xls"):
        formula_cells = _formula_cells(path)
        assert {(4, column) for column in (24, 27, 28, 32, 33, 34, 35, 39)} <= formula_cells


def test_source_identity_is_stable(snapshots):
    assert snapshots["SOBSTV"].source_sha256 == "b9d028306add94c50d2675d5bb7a91335a0ce113ba08b3c01f6184ccb4cefe27"
    assert snapshots["TABYS"].source_sha256 == "2dc88c9ab0cdfb6de04eeb804bdeb63b154265e734670c6f6f612ea60629ff0e"


def test_quality_register_rules_and_coverage_gaps_are_explicit(snapshots):
    common_expected = {
        "DQ-04",
        "DQ-05",
        "DQ-07",
        "DQ-12",
    }
    for snapshot in snapshots.values():
        codes = {issue.code for issue in snapshot.issues}
        assert common_expected <= codes

    sobstv_codes = {issue.code for issue in snapshots["SOBSTV"].issues}
    assert {"DQ-02", "DQ-03"}.isdisjoint(sobstv_codes)
    tabys_codes = {issue.code for issue in snapshots["TABYS"].issues}
    assert all(
        code not in {"DQ-06", "DQ-08", "DQ-09", "DQ-10", "DQ-11", "DQ-13", "DQ-14", "DQ-17", "DQ-18"}
        for code in sobstv_codes | tabys_codes
    )

    tabys_issuer = next(
        position.issuer
        for position in snapshots["TABYS"].positions
        if position.isin == "IE00BQN1K562"
    )
    assert tabys_issuer == "iShares Edge MSCI Europe Quality Factor UCITS"

    sobstv_coverage = next(
        issue for issue in snapshots["SOBSTV"].issues if issue.code == "DQ-12"
    )
    tabys_coverage = next(
        issue for issue in snapshots["TABYS"].issues if issue.code == "DQ-12"
    )
    assert "у 10 лотов нет классификации листинга" in sobstv_coverage.message
    assert "у 14 лотов нет классификации листинга" in tabys_coverage.message


def test_parser_is_independent_of_business_row_numbers():
    path = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"))
    rows = CalamineWorkbook.from_path(path).get_sheet_by_name(SHEET_NAME).to_python(
        skip_empty_area=False
    )
    blank = [""] * 83
    shifted_rows = [blank.copy(), blank.copy(), *rows[:12], blank.copy(), *rows[12:35], blank.copy(), *rows[35:]]

    shifted = _parse_rows(shifted_rows, path, "synthetic-shifted-layout")

    assert len(shifted.positions) == 19
    assert not shifted.raw_settlements
    assert not shifted.settlements
    assert shifted.derived_carrying_value_kzt.quantize(MONEY) == Decimal("4774363156.14")
    assert shifted.cash_kzt.quantize(MONEY) == Decimal("42009877.85")


def test_parser_preserves_osip_balance_price_without_rescaling():
    path = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"))
    rows = CalamineWorkbook.from_path(path).get_sheet_by_name(SHEET_NAME).to_python(
        skip_empty_area=False
    )
    header_index = _find_header_row(rows)
    rows = [row.copy() for row in rows]
    rows[header_index + 2][24] = "97.0100"

    parsed = _parse_rows(rows, path, "synthetic-balance-price")

    assert parsed.positions[0].carrying_price_native == Decimal("97.0100")


@pytest.mark.parametrize(
    ("flag_be", "flag_bf", "expected"),
    [
        (Decimal("1"), Decimal("4"), Decimal("990.6831")),
        (Decimal("3"), Decimal("2"), Decimal("990.6831")),
        (Decimal("1"), Decimal("2"), Decimal("99.06831")),
    ],
)
def test_parser_recalculates_formula_backed_osip_balance_price(
    flag_be, flag_bf, expected
):
    path = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"))
    rows = CalamineWorkbook.from_path(path).get_sheet_by_name(SHEET_NAME).to_python(
        skip_empty_area=False
    )
    header_index = _find_header_row(rows)
    rows = [row.copy() for row in rows]
    row_index = header_index + 2
    rows[row_index][24] = ""
    rows[row_index][11] = 1000
    rows[row_index][16] = 100
    rows[row_index][26] = 99068.31
    rows[row_index][56] = float(flag_be)
    rows[row_index][57] = float(flag_bf)

    parsed = _parse_rows(
        rows,
        path,
        "synthetic-formula-balance-price",
        formula_cells={(row_index, 24)},
    )

    assert parsed.positions[0].carrying_price_native == expected


def test_formula_carrying_price_preserves_osip_unavailable_branches():
    row = [""] * 83
    row[16] = 0
    assert _formula_carrying_price(row) == Decimal("0")

    row[16] = 100
    row[26] = 0
    assert _formula_carrying_price(row) is None

    row[26] = 1000
    row[11] = 0
    row[56] = 1
    row[57] = 2
    assert _formula_carrying_price(row) is None


def test_parser_tolerates_reordered_business_rows():
    path = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"))
    rows = CalamineWorkbook.from_path(path).get_sheet_by_name(SHEET_NAME).to_python(
        skip_empty_area=False
    )
    header_index = _find_header_row(rows)
    business_rows = rows[header_index + 1 :]
    future_header_index = next(
        index
        for index, row in enumerate(business_rows)
        if str(row[0]).strip().casefold().replace("ё", "е") == "предстоящие расчеты"
    )
    reordered_rows = [
        *rows[: header_index + 1],
        *reversed(business_rows[:future_header_index]),
        *business_rows[future_header_index:],
    ]

    reordered = _parse_rows(reordered_rows, path, "synthetic-reordered-layout")

    assert len(reordered.positions) == 19
    assert not reordered.raw_settlements
    assert not reordered.settlements
    assert reordered.derived_operational_total_kzt.quantize(MONEY) == Decimal(
        "4816373033.99"
    )


def test_deposit_closing_on_report_date_fills_in_the_missing_carrying_amount():
    """The source never fills "Балансовая стоимость" for a deposit - it
    puts the equivalent figure in a column shared with repo's closing
    *price* ("Цена закрытия (для репо) / Объем закрытия (для депозита)").
    Confirmed live on a real dashboard upload: a real overnight deposit
    (open and close both on the report date) had this exact shape and
    silently blanked the whole portfolio's derived total before the
    all-or-nothing Overview fix, then stayed correctly excluded-and-disclosed
    after it - this test is the actual root-cause fix: recognise the deposit
    reading of that column so the lot isn't incomplete in the first place."""
    path = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"))
    rows = [
        list(row) for row in
        CalamineWorkbook.from_path(path).get_sheet_by_name(SHEET_NAME).to_python(skip_empty_area=False)
    ]
    header_index = _find_header_row(rows)
    columns = _resolve_columns(rows[header_index])
    report_date = _find_report_date(rows[: header_index + 1])
    deposit_row_index = 6
    assert rows[deposit_row_index][columns["security_code"]] == "NITCb1"
    row = rows[deposit_row_index]
    row[columns["carrying_amount_native"]] = ""
    row[columns["security_type"]] = "депозит"
    row[columns["close_date"]] = report_date
    row[columns["accrued_income_kzt"]] = ""
    row[columns["deposit_closing_amount_native"]] = 5_000_000

    parsed = _parse_rows(rows, path, "synthetic-deposit-closing-on-report-date")

    deposit = next(position for position in parsed.positions if position.security_code == "NITCb1")
    assert "carrying_amount_native" not in deposit.unavailable_fields
    assert deposit.carrying_amount_native == Decimal("5000000")
    assert deposit.derived_carrying_value_kzt == Decimal("5000000")


def test_deposit_closing_before_report_date_does_not_borrow_the_maturity_value():
    """A deposit that hasn't closed yet must stay excluded rather than
    borrowing this column's value - before maturity it's the deposit's full
    value at close (principal + all future interest, not yet earned), and
    using it as *today's* carrying value would overstate the portfolio."""
    path = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"))
    rows = [
        list(row) for row in
        CalamineWorkbook.from_path(path).get_sheet_by_name(SHEET_NAME).to_python(skip_empty_area=False)
    ]
    header_index = _find_header_row(rows)
    columns = _resolve_columns(rows[header_index])
    report_date = _find_report_date(rows[: header_index + 1])
    deposit_row_index = 6
    row = rows[deposit_row_index]
    row[columns["carrying_amount_native"]] = ""
    row[columns["security_type"]] = "депозит"
    row[columns["close_date"]] = date(report_date.year, report_date.month, report_date.day + 1)
    row[columns["deposit_closing_amount_native"]] = 5_000_000

    parsed = _parse_rows(rows, path, "synthetic-deposit-closing-after-report-date")

    deposit = next(position for position in parsed.positions if position.security_code == "NITCb1")
    assert "carrying_amount_native" in deposit.unavailable_fields
    assert deposit.carrying_amount_native is None
    assert deposit.derived_carrying_value_kzt is None
    dq01 = next(issue for issue in parsed.issues if issue.code == "DQ-01" and "NITCb1" in issue.message)
    # Generic message → someone acknowledged and published through it without
    # realizing the cause. The message must point a reviewer at the actual
    # fix (a hidden column) instead of just saying "blocked".
    assert "другим заголовком" in dq01.message


def test_parser_rejects_changed_column_contract():
    path = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"))
    rows = CalamineWorkbook.from_path(path).get_sheet_by_name(SHEET_NAME).to_python(
        skip_empty_area=False
    )
    header_index = _find_header_row(rows)
    rows[header_index][6] = "CHANGED ISIN HEADER"

    with pytest.raises(OsipWorkbookError, match="стабильному контракту столбцов"):
        _parse_rows(rows, path, "synthetic-changed-header")


def test_trailing_blank_rows_raise_dq16(tmp_path):
    path = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"))
    rows = CalamineWorkbook.from_path(path).get_sheet_by_name(SHEET_NAME).to_python(
        skip_empty_area=False
    )
    blank_row = [""] * 83
    padded_rows = [*rows, *([blank_row.copy()] * 50)]

    padded = _parse_rows(padded_rows, path, "synthetic-trailing-blank-rows")
    assert any(issue.code == "DQ-16" for issue in padded.issues)

    baseline = _parse_rows(rows, path, "synthetic-baseline")
    assert not any(issue.code == "DQ-16" for issue in baseline.issues)


def test_sanitized_golden_fixture_preserves_contract_and_lineage():
    fixture_path = Path(__file__).parent / "fixtures" / "sanitized_osip_rows.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    rows = []
    for sparse_row in fixture["rows"]:
        row = [""] * 83
        for index, value in sparse_row.items():
            row[int(index)] = value
        rows.append(row)

    snapshot = _parse_rows(
        rows,
        Path(fixture["source_name"]),
        "sanitized-fixture-v1",
        portfolio_code="TABYS",
    )

    assert snapshot.portfolio_code == "TABYS"
    assert len(snapshot.positions) == 1
    assert len(snapshot.raw_settlements) == 2
    assert len(snapshot.settlements) == 1
    assert len(snapshot.settlements[0].source_refs) == 2
    assert len(snapshot.cash_balances) == 1
    assert snapshot.purchase_amount_kzt == Decimal("48000")
    assert snapshot.derived_carrying_value_kzt == Decimal("50010")
    assert snapshot.cash_kzt == Decimal("1000")
    assert snapshot.derived_operational_total_kzt == Decimal("51010")
    assert {"DQ-01", "DQ-02", "DQ-03", "DQ-04", "DQ-05"} <= {
        issue.code for issue in snapshot.issues
    }
