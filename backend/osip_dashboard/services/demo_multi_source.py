"""Sanitized, generated multi-source examples for the local demo only."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import hashlib
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from osip_dashboard.persistence.models import (
    ClientIdentityResolution,
    DatasetAuditEvent,
    DatasetIssue,
    DatasetRecord,
    DatasetVersion,
    ImportStatus,
    SourceUpload,
)
from osip_dashboard.services.multi_source import approve_dataset, publish_dataset, reconcile_fund
from osip_dashboard.storage import BlobStore


def seed_multi_source_demo(session: Session, blob_store: BlobStore) -> None:
    if session.scalar(select(DatasetVersion.id).limit(1)) is not None:
        _upgrade_sanitized_demo(session)
        reconcile_fund(session, "TABYS")
        return
    fund = _upload(session, blob_store, "demo_tabys_valuation.xlsx", "tabys_valuation")
    brokerage = _upload(session, blob_store, "demo_brokerage.xlsx", "client_brokerage")
    corpfin = _upload(session, blob_store, "demo_corporate_finance.xlsx", "corporate_finance")
    accounting = _upload(session, blob_store, "demo_accounting_landing.xlsx", "accounting_budget_landing")

    _published(session, fund, "fund_valuation", "valuation", "fund", "TABYS", date(2026, 7, 19),
        {"securities_value_kzt": "63573512.02", "cash_kzt": "417484.76", "liabilities_kzt": "98179.77", "nav_kzt": "63892817.01", "units": "105.06954", "unit_value_kzt": "608100.2830"},
        [("valuation", "TABYS", {"nav_kzt": "63892817.01", "unit_value_kzt": "608100.2830", "currency": "KZT"})])
    _published(session, fund, "fund_holdings", "holdings", "fund", "TABYS", date(2026, 7, 19), {"holding_count": 2}, [
        ("holding", "KZDEMO000001", {"instrument": "Demo KZT Bond", "isin": "KZDEMO000001", "issuer": "Demo Issuer A", "quantity": "1000", "currency": "KZT", "purchase_value_kzt": "40000000"}),
        ("holding", "USDEMO000002", {"instrument": "Demo Global ETF", "isin": "USDEMO000002", "issuer": "Demo ETF Trust", "quantity": "75", "currency": "USD", "purchase_value_kzt": "23573512.02"}),
    ])
    _published(session, fund, "fund_unit_series", "TABYS", "fund", "TABYS", date(2026, 7, 19), {"observation_count": 2, "latest_date": "2026-07-19", "active": True}, [
        ("unit_observation", "2026-07-18", {"date": "2026-07-18", "nav_kzt": "63790000", "units": "105.06954", "investors": "120", "unit_value_kzt": "607100.10"}),
        ("unit_observation", "2026-07-19", {"date": "2026-07-19", "nav_kzt": "63892817.01", "units": "105.06954", "investors": "121", "unit_value_kzt": "608100.2830"}),
    ])
    _seed_brokerage_demo(session, brokerage)
    _published(session, corpfin, "corporate_finance_register", "deals", "business_domain", "CORPFIN", date(2026, 6, 30), {"deal_count": 1, "active_count": 1, "period": "1H2026"}, [("deal", "DEMO-DEAL-001", {"issuer": "Demo Corporate Issuer", "subject": "Demo bond placement", "isins": ["KZDEMO000004"], "placement_amount": "1000000000", "placement_currency": "KZT", "placement_raw": "1.0B KZT", "satisfied_demand": "750000000", "demand_currency": "KZT", "demand_raw": "750M KZT", "investors": "5", "commission_rate": "0.25", "fee_received_kzt": "2500000", "duration_raw": "90 дней, проект действующий", "active": True})])

    risk_sobstv = _upload(session, blob_store, "demo_risk_sobstv.xlsx", "risk_limits_sobstv")
    risk_tabys = _upload(session, blob_store, "demo_risk_tabys.xlsx", "risk_limits_tabys")
    _published(session, risk_sobstv, "risk_limits_sobstv", "limits", "business_domain", "SOBSTV", date(2026, 7, 1), {"limit_count": 2, "breach_count": 0}, [
        ("risk_limit", "instrument_category:demo-1", {"dimension": "instrument_category", "label": "Деньги, обратное РЕПО, вклады, в том числе:", "limit_kzt": "4763236555.94", "actual_pct": "0.4051", "actual_kzt": "1929618863.37", "free_limit_kzt": "2833617692.57", "signal": "OK", "portfolio_code": "SOBSTV"}),
        ("risk_limit", "issuer:demo-1", {"dimension": "issuer", "label": "Demo Issuer A", "limit_kzt": "1073063250", "limit_pct": "0.225", "actual_kzt": "949184.22", "actual_pct": "0.0009", "free_limit_kzt": "1072114065.78", "base_label": "Капитал", "signal": "OK", "portfolio_code": "SOBSTV"}),
    ])
    _published(session, risk_tabys, "risk_limits_tabys", "limits", "business_domain", "TABYS", date(2026, 6, 30), {"limit_count": 2, "breach_count": 0}, [
        ("risk_limit", "country:demo-1", {"dimension": "country", "label": "ИРЛАНДИЯ", "limit_kzt": "65978492.25", "limit_pct": "1.0", "actual_kzt": "7784282.06", "actual_pct": "0.118", "free_limit_kzt": "58194210.20", "signal": "OK", "portfolio_code": "TABYS"}),
        ("risk_limit", "issuer:demo-1", {"dimension": "issuer", "label": "Demo ETF Trust", "limit_kzt": "12535913.53", "limit_pct": "0.19", "actual_kzt": "2587460.39", "actual_pct": "0.039", "free_limit_kzt": "9948453.14", "signal": "OK", "portfolio_code": "TABYS"}),
    ])

    statements = _upload(session, blob_store, "demo_accounting_statements.xlsx", "accounting_statements")
    _published(session, statements, "accounting_balance_sheet", "balance_sheet", "business_domain", "ACCOUNTING", date(2026, 7, 1),
        {"line_count": 3, "total_assets_kzt": "4200000", "total_liabilities_kzt": "200000", "total_equity_kzt": "4000000"}, [
        ("balance_sheet_line", "25", {"line_code": "25", "line_label": "Итого активы", "section": "Активы", "current_period_kzt": "4200000", "prior_period_kzt": "4000000"}),
        ("balance_sheet_line", "42", {"line_code": "42", "line_label": "Итого обязательства", "section": "Обязательства", "current_period_kzt": "200000", "prior_period_kzt": "171372"}),
        ("balance_sheet_line", "52", {"line_code": "52", "line_label": "Итого капитал", "section": "Собственный капитал", "current_period_kzt": "4000000", "prior_period_kzt": "3828628"}),
    ])
    _published(session, statements, "accounting_income_statement", "income_statement", "business_domain", "ACCOUNTING", date(2026, 7, 1),
        {"line_count": 3, "total_income_kzt": "287651", "total_expenses_kzt": "184920", "net_profit_kzt": "102731"}, [
        ("income_statement_line", "13", {"line_code": "13", "line_label": "Итого доходов", "quarter_kzt": "287651", "ytd_kzt": "695279", "prior_quarter_kzt": "446018", "prior_ytd_kzt": "1016651"}),
        ("income_statement_line", "28", {"line_code": "28", "line_label": "Итого расходов", "quarter_kzt": "184920", "ytd_kzt": "388685", "prior_quarter_kzt": "365752", "prior_ytd_kzt": "714003"}),
        ("income_statement_line", "29", {"line_code": "29", "line_label": "Чистая прибыль (убыток) до уплаты корпоративного подоходного налога", "quarter_kzt": "102731", "ytd_kzt": "306594", "prior_quarter_kzt": "80266", "prior_ytd_kzt": "302648"}),
    ])

    budget = _upload(session, blob_store, "demo_accounting_budget.xlsx", "accounting_budget_detail")
    _published(session, budget, "accounting_budget", "budget_detail", "business_domain", "ACCOUNTING", date(2025, 9, 30),
        {"line_count": 2, "income_statement_line_count": 1, "cash_flow_line_count": 0, "balance_line_count": 1}, [
        ("budget_line", "income_statement:Процентные доходы", {"section": "income_statement", "line_label": "Процентные доходы", "year_2023_kzt": "476898", "year_2024_kzt": "533775", "budget_9m_2025_kzt": "413412.61", "actual_9m_2025_kzt": "494928", "budget_2025_kzt": "545868.90", "oct_2025_kzt": "44096.42", "nov_2025_kzt": "44164.49", "dec_2025_kzt": "44195.38", "forecast_2025_kzt": "627384.29", "execution_pct": "1.1493", "deviation_kzt": "81515.39"}),
        ("budget_line", "balance:Касса и корр.счета", {"section": "balance", "line_label": "Касса и корр.счета", "year_2023_kzt": "4337", "year_2024_kzt": "42923", "budget_9m_2025_kzt": "69416.32", "actual_9m_2025_kzt": "192403", "budget_2025_kzt": "65240.46", "forecast_2025_kzt": "192403", "execution_pct": "2.9491", "deviation_kzt": "127162.54"}),
        # The cash-flow section of the real budget workbook has row labels
        # but no populated values yet - the demo intentionally seeds zero
        # cash_flow rows too, so the local demo shows the same honest empty
        # state as production rather than a misleadingly "complete" fixture.
    ])
    portfolio_detail = _upload(session, blob_store, "demo_accounting_portfolio.xlsx", "accounting_portfolio_detail_source")
    _published(session, portfolio_detail, "accounting_portfolio_detail", "portfolio_detail", "business_domain", "ACCOUNTING", date(2026, 7, 17),
        {"position_count": 2, "total_carrying_value_kzt": "93858456.64", "total_market_value_kzt": "94685895.85", "total_reserve_kzt": "94885.25"}, [
        ("portfolio_position", "US526057CD41:5", {"category": "Корпоративные облигации", "security_code": "LEN 4.75 11/29/27 Corp", "isin": "US526057CD41", "security_type": "Корпоративные облигации", "issuer": "Demo Issuer A", "coupon_rate": "0.0475", "nominal": "1000", "currency": "USD", "quantity": "99", "purchase_price": "98.8868", "purchase_value_kzt": "44361354.46", "carrying_value_kzt": "46858456.64", "market_value_kzt": "47148443.87", "reserve_kzt": "36045.46", "accrued_income_kzt": "289987.24"}),
        ("portfolio_position", "US78462F1030:9", {"category": "ETF", "security_code": "SPY US", "isin": "US78462F1030", "security_type": "АКЦИИ", "issuer": "Demo ETF Trust", "coupon_rate": None, "nominal": "1", "currency": "USD", "quantity": "213", "purchase_price": "688.17", "purchase_value_kzt": "73622842.08", "carrying_value_kzt": "47000000", "market_value_kzt": "47537452.21", "reserve_kzt": "58839.79", "accrued_income_kzt": None}),
    ])

    landing = DatasetVersion(source_upload=accounting, dataset_type="accounting_landing", detected_key="budget", scope_type="business_domain", scope_code="ACCOUNTING", source_report_date=date(2026, 7, 1), business_date=date(2026, 7, 1), parser_version="sanitized-demo-v1", version=1, status=ImportStatus.VALIDATED, summary={"sheet_count": 1, "publication_basis": "landing_only"}, uploader_id="e2e-uploader")
    session.add(landing); session.flush()
    landing.records.append(_record(landing, "sheet_evidence", "Бюджет", {"sheet": "Бюджет", "rows": 24, "columns": 12, "formula_error_count": 1, "dates": ["2026-07-01"]}))
    landing.issues.append(DatasetIssue(code="ACCOUNTING-00", severity="high", message="Источник сохранён только для предварительного контроля; финансовые показатели не публикуются", affected_fields=["publication"], source_refs=[{"sheet_name": "Бюджет", "row_number": 1}]))
    session.flush()


def _seed_brokerage_demo(session: Session, brokerage: SourceUpload) -> None:
    """Publish every client/brokerage dataset type against one upload.

    Eight clients across three managers/two categories, several holding
    more than one position and some sharing an issuer - enough spread for
    the manager-distribution chart, the concentration/composition charts,
    and the maturity calendar to show something other than a single bar.
    All names/IINs/ISINs are synthetic (see the module docstring); this is
    the only client/brokerage data the demo has now that the real source
    workbook (Клиентский_дашборд.xlsx) is no longer available. Factored out
    so _upgrade_sanitized_demo can also call it against an already-seeded
    demo database that still has the old, much thinner (2-client, no
    maturity calendar/dashboard) version of this data.
    """
    _published(session, brokerage, "brokerage_trade_ledger", "trades", "business_domain", "BROKERAGE", date(2026, 7, 17), {"trade_count": 7, "gross_turnover_by_currency": {"KZT": "38700000"}, "buy_turnover_by_currency": {"KZT": "27700000"}, "sell_turnover_by_currency": {"KZT": "11000000"}, "venue_mix": {"KASE": 5, "AIX": 2}, "instrument_mix": {"Облигации": 5, "Фонды": 2}, "execution_status_mix": {"Исполнено": 6, "В обработке": 1}}, [
        ("trade", "D-001", {"trade_date": "2026-07-14", "side": "Покупка", "client_name": "Demo Client One", "account": "DEMO-001", "venue": "KASE", "isin": "KZDEMO000001", "amount": "10000000", "currency": "KZT", "execution_status": "Исполнено"}),
        ("trade", "D-002", {"trade_date": "2026-07-14", "side": "Продажа", "client_name": "Demo Client Two", "account": "DEMO-002", "venue": "KASE", "isin": "KZDEMO000003", "amount": "5000000", "currency": "KZT", "execution_status": "Исполнено"}),
        ("trade", "D-003", {"trade_date": "2026-07-15", "side": "Покупка", "client_name": "ТОО «Демо Корпорация Три»", "account": "DEMO-003", "venue": "KASE", "isin": "KZDEMO000002", "amount": "8500000", "currency": "KZT", "execution_status": "Исполнено"}),
        ("trade", "D-004", {"trade_date": "2026-07-16", "side": "Покупка", "client_name": "Demo Client Five", "account": "DEMO-005", "venue": "AIX", "isin": "KZDEMO000001", "amount": "3200000", "currency": "KZT", "execution_status": "Исполнено"}),
        ("trade", "D-005", {"trade_date": "2026-07-16", "side": "Продажа", "client_name": "ТОО «Демо Инвест Шесть»", "account": "DEMO-006", "venue": "KASE", "isin": "KZDEMO000006", "amount": "6000000", "currency": "KZT", "execution_status": "В обработке"}),
        ("trade", "D-006", {"trade_date": "2026-07-17", "side": "Покупка", "client_name": "Demo Client Eight", "account": "DEMO-008", "venue": "KASE", "isin": "KZDEMO000004", "amount": "4100000", "currency": "KZT", "execution_status": "Исполнено"}),
        ("trade", "D-007", {"trade_date": "2026-07-17", "side": "Покупка", "client_name": "Demo Client Seven", "account": "DEMO-007", "venue": "AIX", "isin": "KZDEMO000002", "amount": "1900000", "currency": "KZT", "execution_status": "Исполнено"}),
    ])
    _published(session, brokerage, "derivatives_register", "derivatives", "business_domain", "BROKERAGE", date(2026, 7, 31), {"derivative_count": 3}, [
        ("derivative", "DRV-001", {"instrument": "Demo FX Forward", "quantity": "100000", "currency": "USD", "maturity_date": "2026-08-31"}),
        ("derivative", "DRV-002", {"instrument": "Demo FX Swap", "quantity": "50000", "currency": "EUR", "maturity_date": "2026-09-20"}),
        ("derivative", "DRV-003", {"instrument": "Demo Rate Option", "quantity": "20000000", "currency": "KZT", "maturity_date": "2026-12-15"}),
    ])
    _published(session, brokerage, "client_account_snapshot", "clients", "business_domain", "BROKERAGE", date(2026, 7, 20), {"client_count": 8, "position_count": 10, "cash_kzt": "16050000", "total_assets_kzt": "165900000"}, [
        ("client", "DEMO-001", {"record_type": "client", "client_name": "Demo Client One", "account": "DEMO-001", "iin": "000000000001", "branch": "Demo Branch 1", "category": "VIP", "manager": "Demo Manager A", "cash_kzt": "2000000", "total_assets_kzt": "18000000"}),
        ("client", "DEMO-002", {"record_type": "client", "client_name": "Demo Client Two", "account": "DEMO-002", "iin": "000000000002", "branch": "Demo Branch 1", "category": "Retail", "manager": "Demo Manager A", "cash_kzt": "1000000", "total_assets_kzt": "10000000"}),
        ("client", "DEMO-003", {"record_type": "client", "client_name": "ТОО «Демо Корпорация Три»", "account": "DEMO-003", "iin": "000000000003", "branch": "Demo Branch 2", "category": "VIP", "manager": "Demo Manager B", "cash_kzt": "3500000", "total_assets_kzt": "42000000"}),
        ("client", "DEMO-004", {"record_type": "client", "client_name": "Demo Client Four", "account": "DEMO-004", "iin": "000000000004", "branch": "Demo Branch 2", "category": "Retail", "manager": "Demo Manager B", "cash_kzt": "800000", "total_assets_kzt": "6500000"}),
        ("client", "DEMO-005", {"record_type": "client", "client_name": "Demo Client Five", "account": "DEMO-005", "iin": "000000000005", "branch": "Demo Branch 1", "category": "Retail", "manager": "Demo Manager C", "cash_kzt": "1200000", "total_assets_kzt": "9800000"}),
        ("client", "DEMO-006", {"record_type": "client", "client_name": "ТОО «Демо Инвест Шесть»", "account": "DEMO-006", "iin": "000000000006", "branch": "Demo Branch 2", "category": "VIP", "manager": "Demo Manager C", "cash_kzt": "5000000", "total_assets_kzt": "61000000"}),
        ("client", "DEMO-007", {"record_type": "client", "client_name": "Demo Client Seven", "account": "DEMO-007", "iin": "000000000007", "branch": "Demo Branch 1", "category": "Retail", "manager": "Demo Manager A", "cash_kzt": "450000", "total_assets_kzt": "3200000"}),
        ("client", "DEMO-008", {"record_type": "client", "client_name": "Demo Client Eight", "account": "DEMO-008", "iin": "000000000008", "branch": "Demo Branch 2", "category": "Retail", "manager": "Demo Manager B", "cash_kzt": "2100000", "total_assets_kzt": "15400000"}),
        ("client_position", "DEMO-001:KZDEMO000001", {"record_type": "client_position", "client_name": "Demo Client One", "account": "DEMO-001", "issuer": "Demo Issuer A", "isin": "KZDEMO000001", "instrument": "Demo KZT Bond", "quantity": "25"}),
        ("client_position", "DEMO-002:KZDEMO000003", {"record_type": "client_position", "client_name": "Demo Client Two", "account": "DEMO-002", "issuer": "Demo Issuer B", "isin": "KZDEMO000003", "instrument": "Demo USD Bond", "quantity": "12"}),
        ("client_position", "DEMO-003:KZDEMO000002", {"record_type": "client_position", "client_name": "ТОО «Демо Корпорация Три»", "account": "DEMO-003", "issuer": "Demo ETF Trust", "isin": "KZDEMO000002", "instrument": "Demo ETF Fund", "quantity": "40"}),
        ("client_position", "DEMO-003:KZDEMO000004", {"record_type": "client_position", "client_name": "ТОО «Демо Корпорация Три»", "account": "DEMO-003", "issuer": "Demo Issuer C", "isin": "KZDEMO000004", "instrument": "Demo Corporate Bond", "quantity": "20"}),
        ("client_position", "DEMO-004:KZDEMO000005", {"record_type": "client_position", "client_name": "Demo Client Four", "account": "DEMO-004", "issuer": "Demo Equity Co", "isin": "KZDEMO000005", "instrument": "Demo Equity Share", "quantity": "100"}),
        ("client_position", "DEMO-005:KZDEMO000001", {"record_type": "client_position", "client_name": "Demo Client Five", "account": "DEMO-005", "issuer": "Demo Issuer A", "isin": "KZDEMO000001", "instrument": "Demo KZT Bond", "quantity": "15"}),
        ("client_position", "DEMO-006:KZDEMO000003", {"record_type": "client_position", "client_name": "ТОО «Демо Инвест Шесть»", "account": "DEMO-006", "issuer": "Demo Issuer B", "isin": "KZDEMO000003", "instrument": "Demo USD Bond", "quantity": "30"}),
        ("client_position", "DEMO-006:KZDEMO000006", {"record_type": "client_position", "client_name": "ТОО «Демо Инвест Шесть»", "account": "DEMO-006", "issuer": "Demo Issuer D", "isin": "KZDEMO000006", "instrument": "Demo Eurobond", "quantity": "10"}),
        ("client_position", "DEMO-007:KZDEMO000002", {"record_type": "client_position", "client_name": "Demo Client Seven", "account": "DEMO-007", "issuer": "Demo ETF Trust", "isin": "KZDEMO000002", "instrument": "Demo ETF Fund", "quantity": "8"}),
        ("client_position", "DEMO-008:KZDEMO000004", {"record_type": "client_position", "client_name": "Demo Client Eight", "account": "DEMO-008", "issuer": "Demo Issuer C", "isin": "KZDEMO000004", "instrument": "Demo Corporate Bond", "quantity": "18"}),
    ])
    _published(session, brokerage, "client_open_dates", "open_dates", "business_domain", "BROKERAGE", date(2026, 7, 20), {"reference_count": 8, "exact_matches": 8, "unmatched": 0, "ambiguous": 0}, [
        ("client_open_date", "DEMO CLIENT ONE", {"client_name": "Demo Client One", "account": "DEMO-001", "opening_date": "2024-01-15", "match_status": "exact"}),
        ("client_open_date", "DEMO CLIENT TWO", {"client_name": "Demo Client Two", "account": "DEMO-002", "opening_date": "2025-03-20", "match_status": "exact"}),
        ("client_open_date", "ТОО «ДЕМО КОРПОРАЦИЯ ТРИ»", {"client_name": "ТОО «Демо Корпорация Три»", "account": "DEMO-003", "opening_date": "2022-06-10", "match_status": "exact"}),
        ("client_open_date", "DEMO CLIENT FOUR", {"client_name": "Demo Client Four", "account": "DEMO-004", "opening_date": "2025-08-01", "match_status": "exact"}),
        ("client_open_date", "DEMO CLIENT FIVE", {"client_name": "Demo Client Five", "account": "DEMO-005", "opening_date": "2023-11-05", "match_status": "exact"}),
        ("client_open_date", "ТОО «ДЕМО ИНВЕСТ ШЕСТЬ»", {"client_name": "ТОО «Демо Инвест Шесть»", "account": "DEMO-006", "opening_date": "2021-09-18", "match_status": "exact"}),
        ("client_open_date", "DEMO CLIENT SEVEN", {"client_name": "Demo Client Seven", "account": "DEMO-007", "opening_date": "2026-02-14", "match_status": "exact"}),
        ("client_open_date", "DEMO CLIENT EIGHT", {"client_name": "Demo Client Eight", "account": "DEMO-008", "opening_date": "2024-07-30", "match_status": "exact"}),
    ])
    _published(session, brokerage, "client_maturity_calendar", "maturity_calendar", "business_domain", "BROKERAGE", date(2026, 7, 20), {"event_count": 5, "total_value_kzt": "13900000", "nearest_maturity_date": "2026-09-15", "latest_maturity_date": "2027-02-10"}, [
        ("maturity_event", "Demo Client One:Demo KZT Bond:2026-09-15:1", {"client_name": "Demo Client One", "manager": "Demo Manager A", "instrument": "Demo KZT Bond", "isin": "KZDEMO000001", "maturity_date": "2026-09-15", "coupon_payment_date": "2026-09-15", "coupon_percent": "7.5", "days_to_maturity": "59", "value_kzt": "2500000"}),
        ("maturity_event", "Demo Client Five:Demo KZT Bond:2026-09-15:2", {"client_name": "Demo Client Five", "manager": "Demo Manager C", "instrument": "Demo KZT Bond", "isin": "KZDEMO000001", "maturity_date": "2026-09-15", "coupon_payment_date": "2026-09-15", "coupon_percent": "7.5", "days_to_maturity": "59", "value_kzt": "1500000"}),
        ("maturity_event", "ТОО «Демо Корпорация Три»:Demo Corporate Bond:2026-11-30:3", {"client_name": "ТОО «Демо Корпорация Три»", "manager": "Demo Manager B", "instrument": "Demo Corporate Bond", "isin": "KZDEMO000004", "maturity_date": "2026-11-30", "coupon_payment_date": "2026-11-30", "coupon_percent": "6.2", "days_to_maturity": "135", "value_kzt": "3800000"}),
        ("maturity_event", "Demo Client Eight:Demo Corporate Bond:2026-11-30:4", {"client_name": "Demo Client Eight", "manager": "Demo Manager B", "instrument": "Demo Corporate Bond", "isin": "KZDEMO000004", "maturity_date": "2026-11-30", "coupon_payment_date": "2026-11-30", "coupon_percent": "6.2", "days_to_maturity": "135", "value_kzt": "1900000"}),
        ("maturity_event", "ТОО «Демо Инвест Шесть»:Demo Eurobond:2027-02-10:5", {"client_name": "ТОО «Демо Инвест Шесть»", "manager": "Demo Manager C", "instrument": "Demo Eurobond", "isin": "KZDEMO000006", "maturity_date": "2027-02-10", "coupon_payment_date": "2027-02-10", "coupon_percent": "5.0", "days_to_maturity": "207", "value_kzt": "4200000"}),
    ])
    _published(session, brokerage, "client_dashboard_snapshot", "client_dashboard", "business_domain", "BROKERAGE", date(2026, 7, 20), {
        "client_count": 8, "cash_kzt": "16050000", "securities_value_kzt": "149850000", "total_assets_kzt": "165900000",
        "manager_mix": {
            "Demo Manager B": {"client_count": 3, "cash_kzt": "6400000", "securities_value_kzt": "57500000", "total_assets_kzt": "63900000"},
            "Demo Manager C": {"client_count": 2, "cash_kzt": "6200000", "securities_value_kzt": "64600000", "total_assets_kzt": "70800000"},
            "Demo Manager A": {"client_count": 3, "cash_kzt": "3450000", "securities_value_kzt": "27750000", "total_assets_kzt": "31200000"},
        },
    }, [
        ("client_summary", "Demo Client One:3", {"client_name": "Demo Client One", "manager": "Demo Manager A", "client_type": "Физическое лицо", "opening_date": "2024-01-15", "cash_kzt": "2000000", "securities_value_kzt": "16000000", "total_assets_kzt": "18000000", "cash_share": "0.1111", "income": "540000", "status": "Активен", "source_key": "DEMO-001"}),
        ("client_summary", "Demo Client Two:4", {"client_name": "Demo Client Two", "manager": "Demo Manager A", "client_type": "Физическое лицо", "opening_date": "2025-03-20", "cash_kzt": "1000000", "securities_value_kzt": "9000000", "total_assets_kzt": "10000000", "cash_share": "0.1000", "income": "300000", "status": "Активен", "source_key": "DEMO-002"}),
        ("client_summary", "ТОО «Демо Корпорация Три»:5", {"client_name": "ТОО «Демо Корпорация Три»", "manager": "Demo Manager B", "client_type": "Юридическое лицо", "opening_date": "2022-06-10", "cash_kzt": "3500000", "securities_value_kzt": "38500000", "total_assets_kzt": "42000000", "cash_share": "0.0833", "income": "1260000", "status": "Активен", "source_key": "DEMO-003"}),
        ("client_summary", "Demo Client Four:6", {"client_name": "Demo Client Four", "manager": "Demo Manager B", "client_type": "Физическое лицо", "opening_date": "2025-08-01", "cash_kzt": "800000", "securities_value_kzt": "5700000", "total_assets_kzt": "6500000", "cash_share": "0.1231", "income": "195000", "status": "Активен", "source_key": "DEMO-004"}),
        ("client_summary", "Demo Client Five:7", {"client_name": "Demo Client Five", "manager": "Demo Manager C", "client_type": "Физическое лицо", "opening_date": "2023-11-05", "cash_kzt": "1200000", "securities_value_kzt": "8600000", "total_assets_kzt": "9800000", "cash_share": "0.1224", "income": "294000", "status": "Активен", "source_key": "DEMO-005"}),
        ("client_summary", "ТОО «Демо Инвест Шесть»:8", {"client_name": "ТОО «Демо Инвест Шесть»", "manager": "Demo Manager C", "client_type": "Юридическое лицо", "opening_date": "2021-09-18", "cash_kzt": "5000000", "securities_value_kzt": "56000000", "total_assets_kzt": "61000000", "cash_share": "0.0820", "income": "1830000", "status": "Активен", "source_key": "DEMO-006"}),
        ("client_summary", "Demo Client Seven:9", {"client_name": "Demo Client Seven", "manager": "Demo Manager A", "client_type": "Физическое лицо", "opening_date": "2026-02-14", "cash_kzt": "450000", "securities_value_kzt": "2750000", "total_assets_kzt": "3200000", "cash_share": "0.1406", "income": "96000", "status": "Активен", "source_key": "DEMO-007"}),
        ("client_summary", "Demo Client Eight:10", {"client_name": "Demo Client Eight", "manager": "Demo Manager B", "client_type": "Физическое лицо", "opening_date": "2024-07-30", "cash_kzt": "2100000", "securities_value_kzt": "13300000", "total_assets_kzt": "15400000", "cash_share": "0.1364", "income": "462000", "status": "Активен", "source_key": "DEMO-008"}),
    ])


def _upgrade_thin_brokerage_demo(session: Session) -> None:
    """Re-seed the client/brokerage demo if it still has the old thin data.

    The real source workbook (Клиентский_дашборд.xlsx) is gone, so the
    sanitized demo is the only client/brokerage data left. Long-running
    demo databases seeded before the richer dataset was added never run
    seed_multi_source_demo's full-reseed body again (it only fires when
    the database has zero DatasetVersion rows), so this detects the old
    version by the absence of client_maturity_calendar - which the old
    seed never produced - and replaces every brokerage-domain
    sanitized-demo-v1 dataset with the current _seed_brokerage_demo output.
    """
    has_maturity_calendar = session.scalar(
        select(DatasetVersion.id).where(
            DatasetVersion.parser_version == "sanitized-demo-v1",
            DatasetVersion.dataset_type == "client_maturity_calendar",
        ).limit(1)
    )
    if has_maturity_calendar is not None:
        return
    brokerage = session.scalar(
        select(SourceUpload).where(SourceUpload.original_filename == "demo_brokerage.xlsx")
    )
    if brokerage is None:
        return
    old_dataset_types = {
        "brokerage_trade_ledger",
        "derivatives_register",
        "client_account_snapshot",
        "client_open_dates",
    }
    old_datasets = list(session.scalars(
        select(DatasetVersion).where(
            DatasetVersion.parser_version == "sanitized-demo-v1",
            DatasetVersion.dataset_type.in_(old_dataset_types),
        )
    ))
    old_dataset_ids = [dataset.id for dataset in old_datasets]
    if old_dataset_ids:
        session.execute(ClientIdentityResolution.__table__.delete().where(ClientIdentityResolution.dataset_id.in_(old_dataset_ids)))
        session.execute(DatasetRecord.__table__.delete().where(DatasetRecord.dataset_id.in_(old_dataset_ids)))
        session.execute(DatasetIssue.__table__.delete().where(DatasetIssue.dataset_id.in_(old_dataset_ids)))
        session.execute(DatasetAuditEvent.__table__.delete().where(DatasetAuditEvent.dataset_id.in_(old_dataset_ids)))
        session.execute(DatasetVersion.__table__.delete().where(DatasetVersion.id.in_(old_dataset_ids)))
        session.flush()
    _seed_brokerage_demo(session, brokerage)
    session.flush()


def _upgrade_sanitized_demo(session: Session) -> None:
    """Keep persistent local demos current without touching real uploaded data."""
    _upgrade_thin_brokerage_demo(session)
    for dataset in session.scalars(
        select(DatasetVersion).where(
            DatasetVersion.parser_version == "sanitized-demo-v1",
            DatasetVersion.dataset_type == "brokerage_trade_ledger",
        )
    ):
        if "mapping" not in dataset.summary:
            dataset.summary = {
                **dataset.summary,
                "mapping": {
                    "header_row": 8,
                    "confidence": "high",
                    "mapping_confirmed": True,
                    "matched_fields": [],
                    "missing_fields": [],
                },
            }
    record = session.scalar(
        select(DatasetRecord)
        .join(DatasetVersion)
        .where(
            DatasetVersion.parser_version == "sanitized-demo-v1",
            DatasetRecord.record_key == "DEMO-DEAL-001",
        )
    )
    if record is None or record.payload.get("placement_amount") is not None:
        return
    payload = dict(record.payload)
    payload.update({
        "placement_amount": "1000000000",
        "placement_currency": "KZT",
        "satisfied_demand": "750000000",
        "demand_currency": "KZT",
    })
    record.payload = payload
    record.cached_values = dict(payload)


def _upload(session: Session, blob_store: BlobStore, filename: str, source_type: str) -> SourceUpload:
    # openpyxl's default active-sheet title is "Sheet", not "Demo" - every
    # _record() below hardcodes source_ref.sheet_name="Demo" (matching
    # detection.sheets=["Demo"] a few lines down), so without renaming it
    # here the source-cell preview endpoint 404s with "workbook sheet
    # unavailable" for every demo/synthetic row (confirmed via E2E: it
    # opens the workbook from blob storage and checks the sheet name
    # against workbook.sheet_names, which would only ever contain "Sheet").
    workbook = Workbook(); workbook.active.title = "Demo"; workbook.active["A1"] = f"Sanitized Portfolio Operations Insight demo fixture: {source_type}"
    buffer = BytesIO(); workbook.save(buffer); content = buffer.getvalue(); digest = hashlib.sha256(content).hexdigest()
    key = blob_store.put(digest, content, suffix=".xlsx")
    upload = SourceUpload(source_sha256=digest, original_filename=filename, storage_key=key, file_format="xlsx", detected_source_type=source_type, detection={"sanitized_demo": True, "sheets": ["Demo"], "datasets": []}, uploader_id="e2e-uploader")
    session.add(upload); session.flush(); return upload


def _published(session: Session, upload: SourceUpload, dataset_type: str, detected_key: str, scope_type: str, scope_code: str, business_date: date, summary: dict, rows: list[tuple[str, str, dict]]) -> DatasetVersion:
    if dataset_type == "brokerage_trade_ledger" and "mapping" not in summary:
        summary = {**summary, "mapping": {"header_row": 8, "confidence": "high", "mapping_confirmed": True, "matched_fields": [], "missing_fields": []}}
    dataset = DatasetVersion(source_upload=upload, dataset_type=dataset_type, detected_key=detected_key, scope_type=scope_type, scope_code=scope_code, source_report_date=business_date, business_date=business_date, parser_version="sanitized-demo-v1", version=1, status=ImportStatus.VALIDATED, summary=summary, uploader_id="e2e-uploader")
    session.add(dataset); session.flush()
    dataset.records.extend(_record(dataset, record_type, key, payload) for record_type, key, payload in rows)
    approve_dataset(session, dataset, "e2e-reviewer", "Sanitized demo fixture independently reviewed", [])
    publish_dataset(session, dataset, "e2e-publisher")
    return dataset


def _record(dataset: DatasetVersion, record_type: str, key: str, payload: dict) -> DatasetRecord:
    # source_cell completes the same already-synthetic reference tuple as
    # sheet_name/row_number below (every demo SourceUpload's blob really is
    # a one-cell placeholder workbook, per _upload) - without it, the
    # frontend's hasExactSourceCell() check never lets a demo row's "open
    # source preview" affordance appear at all, even though the backend's
    # /source-rows/{id}/preview endpoint already resolves DatasetRecord ids
    # against that real blob and would return its placeholder cell content
    # correctly.
    return DatasetRecord(record_type=record_type, record_key=key, payload=payload, raw_values=dict(payload), formulas={}, cached_values=dict(payload), source_ref={"sheet_name": "Demo", "row_number": 1, "source_cell": "A1"})
