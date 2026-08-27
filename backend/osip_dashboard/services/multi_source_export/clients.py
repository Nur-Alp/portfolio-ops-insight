"""Clients analytics summary writer."""

from __future__ import annotations

from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font

from osip_dashboard.persistence.models import DatasetVersion

from .shared import _matches_term, _open_charts_sheet, _summary_decimal, _write_full_mix_table, _write_summary_table_with_chart


def _write_clients_summary(workbook: Workbook, dataset_by_type: dict[str, DatasetVersion], *, term: str = "") -> None:
    dashboard = dataset_by_type.get("client_dashboard_snapshot")
    account = dataset_by_type.get("client_account_snapshot")
    if dashboard is None and account is None:
        return
    # "Сводка клиентов" is already the display name for the raw
    # client_dashboard_snapshot dataset sheet (see _sheet_name) - use a
    # distinct title here so the two don't collide within the same workbook.
    sheet = workbook.create_sheet("Аналитика клиентов")
    sheet.sheet_view.showGridLines = False
    # No frozen panes: this is a dashboard of stacked tables/charts, read
    # chart-first rather than scrolled as a long table - a frozen column A
    # has nothing to do here. Deliberate, documented exception to the
    # workbook navigation standard (docs/export-column-audit.md), enforced
    # by tests/export_compliance.py's _UNFROZEN_DASHBOARD_SHEETS.
    row = 2
    sheet.cell(row, 1, "Аналитика клиентов").font = Font(bold=True, size=14)
    row += 2

    manager_mix: dict[str, Decimal] = {}
    cash_total = Decimal("0")
    securities_total = Decimal("0")
    have_dashboard_data = False
    if dashboard is not None and dashboard.records:
        # client_account_snapshot's own precomputed .summary is frequently
        # incomplete (no securities_value_kzt at all, and a single "Не
        # указано" manager bucket when the source workbook's manager column
        # was blank on that sheet) - client_dashboard_snapshot carries the
        # same figures per real client row instead, so compute fresh from
        # its filtered records rather than trust a stale/thin summary blob.
        normalized_term = term.strip().casefold()
        records = [record for record in dashboard.records if _matches_term(record, normalized_term)]
        for record in records:
            payload = record.payload
            manager = str(payload.get("manager") or "Не указано").strip() or "Не указано"
            assets = _summary_decimal(payload.get("total_assets_kzt"))
            manager_mix[manager] = manager_mix.get(manager, Decimal("0")) + assets
            cash_total += _summary_decimal(payload.get("cash_kzt"))
            securities_total += _summary_decimal(payload.get("securities_value_kzt"))
        have_dashboard_data = bool(records)
    if not have_dashboard_data and account is not None:
        # No client_dashboard_snapshot published for this export - fall back
        # to the older account_snapshot.summary aggregate rather than
        # showing nothing.
        summary = account.summary or {}
        for manager, values in (summary.get("manager_mix") or {}).items():
            manager_mix[manager] = _summary_decimal(values.get("total_assets_kzt", "0"))
        cash_summary = summary.get("cash_kzt")
        securities_summary = summary.get("securities_value_kzt")
        if cash_summary is not None:
            cash_total = _summary_decimal(cash_summary)
        if securities_summary is not None:
            securities_total = _summary_decimal(securities_summary)

    if manager_mix:
        charts_sheet, charts_row = _open_charts_sheet(
            workbook,
            "Источник данных для диаграмм листа «Аналитика клиентов»",
            "Редактируемая таблица-источник диаграммы. Полный список менеджеров остаётся на листе "
            "«Аналитика клиентов»; мелкие доли объединяются в «Прочее» только в данных диаграммы.",
        )
        row, _ = _write_full_mix_table(
            sheet, row, "Активы по менеджерам", manager_mix, charts_sheet=charts_sheet, charts_row=charts_row,
            table_name="ChartDataManager", chart_title="Активы по менеджерам", log_scale=True,
            value_header="Активы, KZT", numeric_format="#,##0.00;[Red](#,##0.00);-",
        )
    if cash_total or securities_total:
        split_rows = [["Денежные средства", cash_total], ["Ценные бумаги", securities_total]]
        row = _write_summary_table_with_chart(
            sheet, row, "Состав активов: деньги против бумаг", ["Категория", "Сумма, KZT"], split_rows,
            numeric_formats={2: "#,##0.00;[Red](#,##0.00);-"}, chart_column=2, chart_title="Деньги против бумаг",
            chart_kind="pie", widths=[24, 24], add_weight=True,
        )
