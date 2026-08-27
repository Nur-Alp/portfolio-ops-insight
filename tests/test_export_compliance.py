"""Structural compliance checks for every Excel export generator.

Runs the automatable part of docs/excel-export-design-standards.md §7
(freeze panes pin column A, no corrupt archive, no Excel error cells, no
overlapping merges) against a real workbook from every export endpoint, so
a generator that drifts from the standard fails a test instead of being
caught by a manual audit pass (as the freeze-pane gap was this session).
"""

from datetime import date
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from osip_dashboard.services import multi_source_export

from export_compliance import assert_workbook_is_compliant
from test_snapshot_api import PUBLISHER, REVIEWER, UPLOADER, approve_and_publish, upload


def _minimal_filterable_workbook(*, title: str = "Table", freeze: str = "B3", second_table: bool = False) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title
    sheet["A1"] = "Metadata"
    sheet.append(["Label", "Value"])
    sheet.append(["One", 1])
    sheet.auto_filter.ref = "A2:B3"
    if second_table:
        sheet.append([])
        sheet.append(["Second label", "Second value"])
        sheet.append(["Two", 2])
        # The last auto_filter range is the later table, matching the
        # deliberate multi-table ``Сделки`` implementation.
        sheet.auto_filter.ref = "A5:B6"
    sheet.freeze_panes = freeze
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_compliance_rejects_continuous_table_when_header_is_not_frozen():
    with pytest.raises(AssertionError, match="freeze exactly below the header"):
        assert_workbook_is_compliant(_minimal_filterable_workbook(freeze="B1"))


def test_compliance_allows_documented_stacked_trade_sheet_exception():
    assert_workbook_is_compliant(
        _minimal_filterable_workbook(title="Сделки", freeze="B3", second_table=True)
    )


@pytest.mark.parametrize("portfolio_code", ["SOBSTV", "TABYS"])
def test_every_snapshot_level_export_is_workbook_compliant(api, workbook_paths, portfolio_code):
    imported = upload(api, workbook_paths[portfolio_code]).json()
    approve_and_publish(api, imported["id"])
    snapshot_id = imported["snapshot_id"]

    endpoints = {
        "holdings": f"/api/v1/snapshots/{snapshot_id}/holdings/export",
        "lots": f"/api/v1/snapshots/{snapshot_id}/lots/export",
        "cash-calendar": f"/api/v1/snapshots/{snapshot_id}/cash-calendar/export",
        "issues": f"/api/v1/snapshots/{snapshot_id}/issues/export",
        "imports-registry": "/api/v1/imports/export",
    }
    for name, url in endpoints.items():
        response = api.get(url, headers=UPLOADER)
        assert response.status_code == 200, f"{name}: {response.text}"
        assert_workbook_is_compliant(response.content)


def test_risk_module_export_is_workbook_compliant():
    sobstv = SimpleNamespace(
        dataset_type="risk_limits_sobstv", summary={},
        records=[SimpleNamespace(
            payload={
                "portfolio_code": "SOBSTV", "dimension": "instrument_category", "label": "Финансовые инструменты",
                "limit_pct": "0.5", "limit_kzt": "4763236555.94", "actual_pct": "0.4051",
                "actual_kzt": "1929618863.37", "free_limit_kzt": "2833617692.57", "signal": "OK",
            },
            record_type="risk_limit", source_ref={"sheet_name": "Лимиты", "row_number": 9},
        )],
        business_date=date(2026, 7, 1), source_report_date=date(2026, 7, 1), version=1, scope_code="SOBSTV",
        source_upload=SimpleNamespace(original_filename="risk-sobstv.xlsx"),
    )
    tabys = SimpleNamespace(
        dataset_type="risk_limits_tabys", summary={},
        records=[SimpleNamespace(
            payload={
                "portfolio_code": "TABYS", "dimension": "country", "label": "Казахстан",
                "limit_pct": "0.3", "limit_kzt": "1000000000.00", "actual_pct": "0.1",
                "actual_kzt": "100000000.00", "free_limit_kzt": "900000000.00", "signal": "OK",
            },
            record_type="risk_limit", source_ref={"sheet_name": "Пр2-16", "row_number": 12},
        )],
        business_date=date(2026, 6, 30), source_report_date=date(2026, 6, 30), version=1, scope_code="TABYS",
        source_upload=SimpleNamespace(original_filename="risk-tabys.xlsx"),
    )
    assert_workbook_is_compliant(multi_source_export.create_module_xlsx("risk", [sobstv, tabys]))


def test_asset_management_module_export_is_workbook_compliant():
    unit_series = SimpleNamespace(
        dataset_type="fund_unit_series", summary={},
        records=[
            SimpleNamespace(payload={"date": "2026-07-01", "unit_value_kzt": "100.0"}, record_type="unit", source_ref={"sheet_name": "S", "row_number": 2}),
            SimpleNamespace(payload={"date": "2026-07-02", "unit_value_kzt": "101.5"}, record_type="unit", source_ref={"sheet_name": "S", "row_number": 3}),
        ],
        business_date=date(2026, 7, 2), source_report_date=date(2026, 7, 2), version=1, scope_code="TABYS",
        source_upload=SimpleNamespace(original_filename="fund.xlsx"),
    )
    holdings = SimpleNamespace(
        dataset_type="fund_holdings", summary={},
        records=[SimpleNamespace(
            payload={
                "currency": "KZT", "purchase_value_kzt": "1000000", "isin": "US1", "instrument": "X",
                "quantity": "10", "purchase_value_native": "1000000", "purchase_date": "2023-01-01",
            },
            record_type="holding", source_ref={"sheet_name": "H", "row_number": 2},
        )],
        business_date=date(2026, 7, 2), source_report_date=date(2026, 7, 2), version=1, scope_code="TABYS",
        source_upload=SimpleNamespace(original_filename="fund.xlsx"),
    )
    assert_workbook_is_compliant(multi_source_export.create_module_xlsx("asset-management", [unit_series, holdings]))


@pytest.mark.parametrize(
    ("module", "dataset_type", "scope_code", "payload"),
    [
        (
            "brokerage",
            "brokerage_trade_ledger",
            "BROKERAGE",
            {
                "trade_number": "T-001", "trade_date": "2026-07-01", "settlement_date": "2026-07-02",
                "side": "Покупка", "venue": "KASE", "instrument": "Demo bond", "issuer": "Demo issuer",
                "security_type": "Bond", "isin": "KZDEMO0001", "quantity": "1", "amount": "100",
                "currency": "KZT", "execution_status": "Исполнено", "failure_reason": "",
            },
        ),
        (
            "corporate-finance",
            "corporate_finance_register",
            "CORPFIN",
            {
                "issuer": "Demo issuer", "subject": "Demo placement", "isins": ["KZDEMO0001"],
                "placement_raw": "100 KZT", "demand_raw": "50 KZT", "investors": "1",
                "commission_rate": "0.1", "fee_received_kzt": "1", "duration_raw": "10 дней", "active": True,
            },
        ),
        (
            "accounting",
            "accounting_balance_sheet",
            "ACCOUNTING",
            {"line_code": "1", "line_label": "Assets", "section": "A", "current_period_kzt": "100", "prior_period_kzt": "90"},
        ),
    ],
)
def test_remaining_module_exports_are_workbook_compliant(module, dataset_type, scope_code, payload):
    dataset = SimpleNamespace(
        dataset_type=dataset_type,
        summary={},
        records=[SimpleNamespace(payload=payload, record_type="row", source_ref={"sheet_name": "Source", "row_number": 2})],
        business_date=date(2026, 7, 1),
        source_report_date=date(2026, 7, 1),
        version=1,
        scope_code=scope_code,
        source_upload=SimpleNamespace(original_filename="demo-source.xlsx"),
    )
    assert_workbook_is_compliant(multi_source_export.create_module_xlsx(module, [dataset]))
