"""Content detection and parsers for non-OSIP Portfolio Operations Insight workbook feeds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from python_calamine import CalamineWorkbook

from osip_dashboard.ingestion.formula_audit import audit_consumed_formula_results, audit_workbook, open_xlsx_pair

from .accounting import (
    _BALANCE_SHEET_SECTIONS,
    _BUDGET_PERIOD_COLUMNS,
    _BUDGET_RATIO_ONLY_LABELS,
    _BUDGET_SECTION_MARKERS,
    _parse_accounting_balance_sheet,
    _parse_accounting_budget,
    _parse_accounting_income_statement,
    _parse_accounting_landing,
    _parse_accounting_portfolio,
)
from .client_brokerage import _parse_client_brokerage
from .corporate_finance import _parse_corporate_finance
from .risk import (
    RISK_NEAR_BREACH_POLICY_VERSION,
    RISK_NEAR_BREACH_THRESHOLD,
    _TABYS_RISK_SECTION_DIMENSIONS,
    _parse_risk_sobstv,
    _parse_risk_tabys,
    _risk_near_breach,
    _risk_signal,
    _risk_summary,
    _risk_utilization,
)
from .shared import (
    OLE_SIGNATURE,
    PARSER_VERSION,
    XLSX_SIGNATURE,
    ParsedDataset,
    ParsedIssue,
    SourceDetectionError,
    _accounting_explicit_dates,
    _as_date,
    _cell,
    _cell_ref,
    _client_position_lookup,
    _client_trade_columns,
    _contains_any,
    _d,
    _date_text,
    _decimal_text,
    _excel_column_letter,
    _explicit_report_date,
    _explicit_report_dates,
    _extract_coupon_rate,
    _extract_date,
    _extract_isins,
    _issue,
    _looks_isin,
    _metric,
    _metric_cell,
    _normalize_header,
    _normalize_name,
    _parse_amount,
    _period_end,
    _period_end_ddmmyy,
    _proposal,
    _record,
    _resolve_calendar_isin,
    _russian_period_end,
    _sheet_names,
    _text,
    _xlsx_contains,
    validate_source_filename,
)
from .tabys import _parse_tabys_valuation, _parse_unit_history

__all__ = [
    "OLE_SIGNATURE",
    "PARSER_VERSION",
    "XLSX_SIGNATURE",
    "ParsedDataset",
    "ParsedIssue",
    "SourceDetectionError",
    "RISK_NEAR_BREACH_POLICY_VERSION",
    "RISK_NEAR_BREACH_THRESHOLD",
    "CalamineWorkbook",
    "detect_source",
    "parse_detected_dataset",
    "validate_source_filename",
    "_explicit_report_dates",
    "_extract_coupon_rate",
    "_extract_isins",
    "_parse_accounting_landing",
    "_parse_amount",
    "_parse_client_brokerage",
    "_parse_corporate_finance",
    "_parse_tabys_valuation",
    "_parse_unit_history",
    "_resolve_calendar_isin",
    "_risk_near_breach",
    "_risk_utilization",
]


def _propose_tabys_valuation(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if "дата" not in names or not _xlsx_contains(path, "дата", "Текущая стоимость портфеля ЦБ"):
        return None
    # "дата" is the only sheet every key below actually needs - report_date
    # and the valuation/cash_liabilities figures all come from it alone,
    # so it's the anchor. "часть 1 (портфель)"/"Цены"/"справка о ст-ти
    # ЧА" each back exactly one of the other keys and nothing else reads
    # them, so each is proposed independently instead of requiring all
    # three to still exist under their original names. inactive_evidence
    # already scans for its own evidence-sheet names by presence (see
    # _parse_tabys_valuation) and degrades to zero records on its own, so
    # it's always safe to offer.
    datasets = [
        _proposal("valuation", "fund_valuation", "fund", "TABYS"),
        _proposal("cash_liabilities", "fund_cash_liabilities", "fund", "TABYS"),
        _proposal("inactive_evidence", "fund_inactive_evidence", "fund", "TABYS"),
    ]
    if "часть 1 (портфель)" in names:
        datasets.append(_proposal("holdings", "fund_holdings", "fund", "TABYS"))
    if "справка о ст-ти ЧА" in names:
        datasets.append(_proposal("nav_history", "fund_nav_history", "fund", "TABYS"))
    if "Цены" in names:
        datasets.append(_proposal("prices", "fund_prices", "fund", "TABYS"))
    return datasets


def _propose_fund_unit_history(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if "Форма" not in names or not _xlsx_contains(path, "Форма", "# Паев в обращении"):
        return None
    # "Лист1" used to be required alongside "Форма" here, but
    # _parse_unit_history never reads it - confirmed nothing in this
    # contract actually depends on it, so it was dead weight that could
    # only ever cause a false rejection, never prevent one.
    return [
        _proposal("SAQ", "fund_unit_series", "fund", "SAQ"),
        _proposal("TABYS", "fund_unit_series", "fund", "TABYS"),
    ]


def _propose_client_brokerage(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if "Лист4" not in names or not _xlsx_contains(path, "Лист4", "Л/счет"):
        return None
    # Лист4 (the account/position register) is the only sheet this
    # contract actually reads to build client_account_snapshot - it's
    # the canonical evidence, everything else here is corroborating
    # detail from the same workbook. A real-world version of this file
    # has already reorganized/renamed Лист8/Лист7/Лист6 while keeping
    # Лист4 unchanged (confirmed on a real "1.1" revision), so each of
    # those - and the two further optional sheets below - is proposed
    # independently, gated on its own presence, rather than requiring
    # the whole historical four-sheet bundle to still exist. A missing
    # sheet just means that one dataset isn't offered, not that the
    # whole workbook is rejected.
    datasets = [_proposal("clients", "client_account_snapshot", "business_domain", "BROKERAGE")]
    if "Лист8" in names and _xlsx_contains(path, "Лист8", "Номер клиентского заказа"):
        datasets.append(_proposal("trades", "brokerage_trade_ledger", "business_domain", "BROKERAGE"))
    if "Лист7" in names:
        datasets.append(_proposal("derivatives", "derivatives_register", "business_domain", "BROKERAGE"))
    if "Лист6" in names:
        datasets.append(_proposal("open_dates", "client_open_dates", "business_domain", "BROKERAGE"))
    if "календарь погашения" in names:
        datasets.append(_proposal("maturity_calendar", "client_maturity_calendar", "business_domain", "BROKERAGE"))
    if "Клиенты" in names:
        datasets.append(_proposal("client_dashboard", "client_dashboard_snapshot", "business_domain", "BROKERAGE"))
    return datasets


def _propose_corporate_finance(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if len(sheets) != 1 or not _contains_any(path, file_format, sheets[0], ("Направление корпоративного финансирования",)):
        return None
    return [_proposal("deals", "corporate_finance_register", "business_domain", "CORPFIN")]


def _propose_risk_limits_sobstv(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if "Лимиты" not in names or "Лимит по странам" not in names:
        return None
    return [_proposal("limits", "risk_limits_sobstv", "business_domain", "SOBSTV")]


def _propose_risk_limits_tabys(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if "Пр2-16" not in names:
        return None
    return [_proposal("limits", "risk_limits_tabys", "business_domain", "TABYS")]


def _propose_accounting_statements(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if "f1_uip" not in names or not _xlsx_contains(path, "f1_uip", "Бухгалтерский баланс"):
        return None
    # f1_uip (balance sheet) and f2_uip (income statement) are parsed
    # entirely independently - _parse_accounting_balance_sheet only ever
    # opens f1_uip, _parse_accounting_income_statement only ever opens
    # f2_uip - so f2_uip is proposed when present rather than required
    # for the whole workbook to be recognized at all.
    datasets = [_proposal("balance_sheet", "accounting_balance_sheet", "business_domain", "ACCOUNTING")]
    if "f2_uip" in names:
        datasets.append(_proposal("income_statement", "accounting_income_statement", "business_domain", "ACCOUNTING"))
    return datasets


def _propose_accounting_budget_landing(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if "Бюджет" not in names or not _contains_any(path, file_format, "Бюджет", ("бюджет", "2026")):
        return None
    return [
        _proposal("budget", "accounting_landing", "business_domain", "ACCOUNTING"),
        _proposal("budget_detail", "accounting_budget", "business_domain", "ACCOUNTING"),
    ]


def _propose_accounting_portfolio_landing(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if "ОСИП_ПОРТФЕЛЬ" not in names or "Лист1" not in names:
        return None
    return [
        _proposal("portfolio", "accounting_landing", "business_domain", "ACCOUNTING"),
        _proposal("portfolio_detail", "accounting_portfolio_detail", "business_domain", "ACCOUNTING"),
    ]


def _propose_osip_portfolio(names: set[str], sheets: list[str], path: Path, file_format: str) -> list[dict[str, str]] | None:
    if "ОСИП_ПОРТФЕЛЬ" not in names:
        return None
    return [_proposal("portfolio", "portfolio_snapshot", "portfolio", "")]


@dataclass(frozen=True)
class _WorkbookContract:
    source_type: str
    propose: Callable[[set[str], list[str], Path, str], list[dict[str, str]] | None]


# Order matters, exactly as it did in the if/elif chain this replaced:
# accounting_portfolio_landing must be checked before osip_portfolio, since
# both match on "ОСИП_ПОРТФЕЛЬ" - "Лист1" is what tells them apart (see
# test_лист1_discriminates_accounting_portfolio_landing_from_standalone_osip
# in tests/test_multi_source.py), and a registry that tried these in a
# different order would silently misdetect one as the other.
_CONTRACTS: tuple[_WorkbookContract, ...] = (
    _WorkbookContract("tabys_valuation", _propose_tabys_valuation),
    _WorkbookContract("fund_unit_history", _propose_fund_unit_history),
    _WorkbookContract("client_brokerage", _propose_client_brokerage),
    _WorkbookContract("corporate_finance", _propose_corporate_finance),
    _WorkbookContract("risk_limits_sobstv", _propose_risk_limits_sobstv),
    _WorkbookContract("risk_limits_tabys", _propose_risk_limits_tabys),
    _WorkbookContract("accounting_statements", _propose_accounting_statements),
    _WorkbookContract("accounting_budget_landing", _propose_accounting_budget_landing),
    _WorkbookContract("accounting_portfolio_landing", _propose_accounting_portfolio_landing),
    _WorkbookContract("osip_portfolio", _propose_osip_portfolio),
)


def detect_source(path: Path, file_format: str) -> dict[str, Any]:
    sheets = _sheet_names(path, file_format)
    names = set(sheets)
    for contract in _CONTRACTS:
        datasets = contract.propose(names, sheets, path, file_format)
        if datasets is not None:
            return {"source_type": contract.source_type, "sheets": sheets, "datasets": datasets}
    raise SourceDetectionError("Структура рабочей книги не соответствует известному контракту источника")


def parse_detected_dataset(
    path: Path, detection: dict[str, Any], detected_key: str, scope_code: str | None = None
) -> ParsedDataset:
    # Every call needs a formula-audit pair regardless of contract type (see
    # below), and the two contracts that scan for external/broken formulas
    # inline (tabys_valuation, fund_unit_history) need one too - opening it
    # once here and threading it through both, instead of each step
    # independently reopening the same file, is what actually closes the
    # remaining redundancy audit_workbook's own memoization doesn't reach
    # (that only helps repeat calls for the *same* upload's other keys, not
    # the first call, and not audit_consumed_formula_results, which depends
    # on per-key records so can't be memoized the same way).
    if Path(path).suffix.casefold() == ".xlsx":
        with open_xlsx_pair(path) as (formulas, cached):
            parsed = _parse_detected_dataset(path, detection, detected_key, scope_code, formula_workbook=formulas, data_workbook=cached)
            audit = audit_workbook(path, workbooks=(formulas, cached))
            consumed_formula_audit = audit_consumed_formula_results(path, parsed.records, workbooks=(formulas, cached))
    else:
        parsed = _parse_detected_dataset(path, detection, detected_key, scope_code)
        audit = audit_workbook(path)
        consumed_formula_audit = audit_consumed_formula_results(path, parsed.records)
    parsed.summary = {
        **parsed.summary,
        "formula_audit": audit,
        "consumed_formula_audit": consumed_formula_audit,
    }
    if consumed_formula_audit["status"] == "blocked":
        refs = tuple(
            {"sheet_name": item["sheet_name"], "source_cell": item["source_cell"]}
            for item in consumed_formula_audit["invalid_cells"]
        )
        fields = tuple(sorted({field for item in consumed_formula_audit["invalid_cells"] for field in item["fields"]}))
        parsed.issues.append(
            ParsedIssue(
                "FORMULA-01",
                "blocker",
                "Используемые показатели содержат пустой или ошибочный сохранённый результат формулы; публикация заблокирована.",
                fields,
                refs,
            )
        )
    by_sheet = audit.get("by_sheet", {})
    for record in parsed.records:
        if record.get("record_type") != "sheet_evidence":
            continue
        sheet_name = record.get("source_ref", {}).get("sheet_name")
        sheet_audit = by_sheet.get(sheet_name)
        if not isinstance(sheet_audit, dict):
            continue
        payload = record.setdefault("payload", {})
        payload.update(sheet_audit)
        # Keep the legacy spelling used by the accounting evidence table.
        if "external_formula_count" in sheet_audit:
            payload["external_link_count"] = sheet_audit["external_formula_count"]
    return parsed


def _parse_detected_dataset(
    path: Path,
    detection: dict[str, Any],
    detected_key: str,
    scope_code: str | None = None,
    *,
    data_workbook: Any = None,
    formula_workbook: Any = None,
) -> ParsedDataset:
    source_type = detection["source_type"]
    proposal = next((item for item in detection["datasets"] if item["key"] == detected_key), None)
    if proposal is None:
        raise SourceDetectionError(f"Раздел источника «{detected_key}» не найден")
    scope = (scope_code or proposal["scope_code"]).strip().upper()
    if not scope:
        raise SourceDetectionError("Для раздела требуется код области данных")
    # Only the two contracts that do their own inline external/broken-formula
    # scan can use a pre-opened pair - every other parser here only ever
    # needs the plain cached-value read it already does on its own, so
    # data_workbook/formula_workbook are silently unused for them rather
    # than threaded through everywhere for consistency's sake.
    if source_type == "tabys_valuation":
        return _parse_tabys_valuation(path, detected_key, scope, data_workbook=data_workbook, formula_workbook=formula_workbook)
    if source_type == "fund_unit_history":
        return _parse_unit_history(path, detected_key, scope, data_workbook=data_workbook, formula_workbook=formula_workbook)
    if source_type == "client_brokerage":
        return _parse_client_brokerage(path, detected_key, scope)
    if source_type == "corporate_finance":
        return _parse_corporate_finance(path, scope)
    if source_type == "accounting_statements":
        if detected_key == "balance_sheet":
            return _parse_accounting_balance_sheet(path, scope)
        if detected_key == "income_statement":
            return _parse_accounting_income_statement(path, scope)
    if source_type == "risk_limits_sobstv":
        return _parse_risk_sobstv(path, scope)
    if source_type == "risk_limits_tabys":
        return _parse_risk_tabys(path, scope)
    if source_type == "accounting_budget_landing" and detected_key == "budget_detail":
        return _parse_accounting_budget(path, scope)
    if source_type == "accounting_portfolio_landing" and detected_key == "portfolio_detail":
        return _parse_accounting_portfolio(path, scope)
    if source_type.startswith("accounting_"):
        return _parse_accounting_landing(path, detection, detected_key, scope, formula_workbook=formula_workbook)
    raise SourceDetectionError("Этот тип источника обрабатывается совместимым импортом OSIP")
