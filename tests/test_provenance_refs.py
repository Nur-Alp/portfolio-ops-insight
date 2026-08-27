from types import SimpleNamespace
from uuid import uuid4

from osip_dashboard.api_handlers import _provenance_ref


def _row(row_number: int = 42):
    return SimpleNamespace(
        workbook_name="portfolio.xls",
        sheet_name="ОСИП_ПОРТФЕЛЬ",
        row_number=row_number,
        parser_version="osip-test",
        id=uuid4(),
    )


def test_osip_provenance_includes_excel_cell_and_column():
    reference = _provenance_ref(_row(), SimpleNamespace(), "report_fx_rate", "498.12")

    assert reference["source_column"] == 47
    assert reference["source_column_letter"] == "AU"
    assert reference["source_cell"] == "AU42"
    assert reference["source_kind"] == "row"


def test_synthetic_provenance_field_keeps_row_without_fabricating_a_cell():
    reference = _provenance_ref(_row(7), SimpleNamespace(), "position_lot", 1)

    assert reference["row_number"] == 7
    assert reference["source_kind"] == "row"
    assert "source_cell" not in reference

