"""Parsers for the risk-limit workbook contracts (SOBSTV and TABYS)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import re
from typing import Any

from osip_dashboard.config import get_settings

from .shared import (
    ParsedDataset,
    ParsedIssue,
    _as_date,
    _cell,
    _d,
    _date_text,
    _decimal_text,
    _issue,
    _normalize_name,
    _period_end_ddmmyy,
    _record,
    _rows_header_columns,
    _text,
)


# Column labels for each risk sheet, resolved by header text (see
# _rows_header_columns) rather than a fixed position - the same brittleness
# class fixed elsewhere in ingestion this session (OSIP/TABYS/accounting):
# a risk-limit workbook column moving would otherwise silently misread a
# breach threshold as an actual value, or vice versa. Aliases are ordered
# label -> limit -> actual -> free_limit, matching every sheet's own
# left-to-right layout: several sheets reuse the exact same sub-header text
# ("%", "В денежном эквиваленте") for different fields under different
# spanning parent headers (e.g. Лимит по МСФО), and this order is what lets
# _rows_header_columns' first-not-yet-claimed-field tie-break resolve them
# correctly - verified against both real SOBSTV/TABYS workbooks this session.
# Row *classification* (which rows are data rows at all - a numeric marker
# in a fixed column, an "Итого" prefix, a 3-letter currency code) is a
# separate, independently-verified concern and is deliberately left as-is.
_RISK_LIMITS_ALIASES: dict[str, tuple[str, ...]] = {
    "label": ("перечень инструментов инвестирования",),
    "limit_kzt": ("утвержденный лимит в денежном эквиваленте",),
    "actual_pct": ("фактические значения (% от собственных активов",),
    "actual_kzt": ("фактические значения в денежном эквиваленте",),
    "free_limit_kzt": ("свободный лимит в денежном эквиваленте",),
}
_RISK_COUNTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "label": ("страна",),
    "limit_usd": ("лимит, долл.сша",),
    "limit_kzt": ("лимит, тенге",),
    "actual_usd": ("фактическое освоение, долл.сша",),
    "free_limit_usd": ("свободный лимит, долл.сша",),
}
_RISK_ISSUER_OR_SECTOR_ALIASES: dict[str, tuple[str, ...]] = {
    "label": ("наименование",),
    "actual_kzt": ("инвестировано в тенге",),
    "limit_kzt": ("лимит в тенге",),
    "actual_pct": ("инвестировано в % от базы лимита",),
    "limit_pct": ("лимит в % от базы лимита",),
    "base_label": ("база лимита",),
    "free_limit_kzt": ("свободный лимит в тенге",),
    "signal_raw": ("сигнал",),
}
_RISK_IFRS_ALIASES: dict[str, tuple[str, ...]] = {
    "label": ("финансовые инструменты в соответствии",),
    "limit_pct": ("%",),
    "limit_kzt": ("в денежном эквиваленте",),
    "actual_pct": ("%",),
    "actual_kzt": ("в денежном эквиваленте",),
    "free_limit_kzt": ("в денежном эквиваленте",),
}
_RISK_DURATION_ALIASES: dict[str, tuple[str, ...]] = {
    "label_alt": ("вид ценной бумаги",),
    "resident_status": ("признак резидентства",),
    "country": ("страна",),
    "sector_gics": ("отрасль gics",),
    "currency": ("валюта",),
    "instrument_type": ("тип ценной бумаги",),
    "credit_rating": ("кредитный рейтинг",),
    "ifrs_method": ("метод мсфо",),
    "duration_limit": ("утвержденный лимит на дюрацию",),
    "modified_duration": ("модифицированная дьюрация",),
    "trading_code": ("торговый код",),
    "isin": ("isin",),
    "issuer": ("наименование эмитента",),
    "carrying_value_native": ("балансовая стоимость в валюте цб",),
    "carrying_value_kzt": ("балансовая стоимость в тенге",),
    "weight_pct": ("уд.вес, %",),
    "coupon_pct": ("ставка купона, %",),
    "ytm_purchase_pct": ("доходность до погашения / ytm при покупке (%)",),
    "ytm_report_pct": ("доходность до погашения / ytm на дату отчета (%)",),
    "maturity_date": ("дата закрытия",),
}
_RISK_EXPOSURE_ALIASES: dict[str, tuple[str, ...]] = {
    "instrument_group": ("тип инструмента",),
    "currency": ("валюта",),
    "amount_native": ("сумма в валюте",),
    "fx_rate": ("курс",),
    "amount_kzt": ("сумма в тенге",),
}
_RISK_TABYS_ALIASES: dict[str, tuple[str, ...]] = {
    "label": ("классификация инвестиции",),
    "limit_pct": ("установленный лимит (%)",),
    "actual_pct": ("фактический размер инвестирования (в % от активов)",),
    "limit_kzt": ("установленный лимит",),
    "actual_kzt": ("фактический размер инвестирования",),
    "signal_raw": ("сигнал",),
}


def _risk_signal(raw: Any, limit_kzt: Any, actual_kzt: Any, limit_usd: Any = None, actual_usd: Any = None) -> str | None:
    """Prefer the source's own OK/breach flag; derive one only when it's absent.

    Any non-"OK" non-blank text is treated as a breach flag rather than
    matched against a fixed vocabulary - the source's own signal wording is
    the authority here, not a guess at what it might say instead of "OK".
    """
    text = _text(raw).upper()
    if text == "OK":
        return "OK"
    if text:
        return "breach"
    limit_value = limit_kzt if limit_kzt not in (None, "") else limit_usd
    actual_value = actual_kzt if actual_kzt not in (None, "") else actual_usd
    if limit_value in (None, ""):
        # Several source sections are intentionally informational: they show
        # exposure but carry no threshold of their own. Do not present those
        # rows as an unresolved control failure.
        return "not_applicable" if actual_value not in (None, "") else None
    if actual_value in (None, ""):
        return None
    try:
        return "breach" if Decimal(str(actual_value)) > Decimal(str(limit_value)) else "OK"
    except (InvalidOperation, ValueError):
        return None


# Near-breach policy: a single global threshold on percentage-of-limit
# utilization (actual / limit), not an absolute-headroom cutoff - limit
# scale varies enormously across dimensions (a country limit might be tens
# of millions KZT, an issuer limit billions), so a fixed absolute cutoff
# would be meaningless across them while a ratio is dimension-agnostic.
# Stored on each record (not computed ad hoc at read time) and stamped with
# the threshold that produced it, so a later policy change is auditable
# against already-published data instead of silently reclassifying it.
_risk_settings = get_settings()
RISK_NEAR_BREACH_THRESHOLD = Decimal(str(_risk_settings.risk_near_breach_threshold))
RISK_NEAR_BREACH_POLICY_VERSION = _risk_settings.risk_near_breach_policy_version


def _risk_utilization(
    limit_pct: Any, actual_pct: Any, limit_kzt: Any, actual_kzt: Any,
    limit_usd: Any = None, actual_usd: Any = None, base_label: Any = None,
) -> Decimal | None:
    """actual/limit as a ratio, preferring %-of-NAV, then KZT, then USD.

    Mirrors _risk_signal's own value-selection order. A ratio (not a
    difference) is used so utilization is comparable across dimensions
    regardless of their absolute limit size.

    base_label is an explicit exception to that %-first preference: it
    names what the source itself says limit_pct is a percentage OF (e.g.
    "Капитал"/capital), a different denominator than actual_pct's own
    (total assets under management). Dividing two percentages of different
    wholes isn't a valid ratio - confirmed on real data, a SOBSTV issuer row
    at 86.2% of assets against a 22.5%-of-capital limit produced a nonsense
    383% "utilization" for a row the source itself reports as OK, because
    limit_kzt/actual_kzt (both genuinely in the same units) agree it's
    within limit. When base_label is set, skip straight to the KZT/USD pair
    instead of the mismatched percentages.
    """
    pairs = ((limit_kzt, actual_kzt), (limit_usd, actual_usd)) if base_label not in (None, "") else (
        (limit_pct, actual_pct), (limit_kzt, actual_kzt), (limit_usd, actual_usd),
    )
    for limit_value, actual_value in pairs:
        if limit_value in (None, "") or actual_value in (None, ""):
            continue
        try:
            limit_decimal = Decimal(str(limit_value))
            if limit_decimal == 0:
                continue
            return Decimal(str(actual_value)) / limit_decimal
        except (InvalidOperation, ValueError):
            continue
    return None


def _risk_near_breach(signal: str | None, utilization: Decimal | None) -> bool:
    if signal == "breach" or utilization is None:
        return False
    # Strictly below 100%: real source data has "OK" rows (e.g. supranational
    # issuers) whose actual/limit ratio is well over 1, because the source's
    # own OK/breach flag overrides a straight actual/limit comparison for
    # that row (_risk_signal always prefers the raw flag over the derived
    # one). Flagging those as near-breach would contradict the source's own
    # signal instead of deferring to it, so the utilization threshold only
    # applies within the band where it cannot disagree with "OK".
    return RISK_NEAR_BREACH_THRESHOLD <= utilization < 1


def _parse_risk_sobstv(path: Path, scope: str) -> ParsedDataset:
    """Unified risk-limit lines for the proprietary (SOBSTV) portfolio.

    Five sheets share a "classification label + approved limit + actual
    investment + free limit" shape and are extracted as one flat table by
    `dimension`: instrument_category ("Лимиты", category-total rows only -
    their "1.1."-style sub-lines are a finer breakdown with no limit of
    their own, deferred), country ("Лимит по странам", USD/KZT-denominated,
    no % figures unlike the others), issuer ("Лимит на Эмитента"), sector
    ("Лимит на Отрасль" - the second, per-sector-deduped block; the first
    block repeats a sector name once per position and shares one blanket
    portfolio-wide "limit" that doesn't actually differ by sector), and
    ifrs ("Лимит по МСФО"). The duration sheet is retained as instrument-level
    duration controls, and "Расшифровка" is retained as currency/instrument
    exposure detail rather than being mixed into the limit-line totals.
    """
    from osip_dashboard.ingestion import multi_source as _multi_source

    workbook = _multi_source.CalamineWorkbook.from_path(path)
    records: list[dict[str, Any]] = []
    issues: list[ParsedIssue] = []
    business_date: date | None = None
    try:
        countries_preview = workbook.get_sheet_by_name("Лимит по странам").to_python(skip_empty_area=False)
        if len(countries_preview) > 1 and len(countries_preview[1]) > 2:
            business_date = _as_date(countries_preview[1][2])
    except Exception:
        business_date = None

    def add_record(
        dimension: str, *, sheet_name: str, row_number: int, row: tuple[Any, ...], label_column: int | None,
        limit_pct_column: int | None = None, limit_kzt_column: int | None = None,
        actual_pct_column: int | None = None, actual_kzt_column: int | None = None,
        free_limit_kzt_column: int | None = None, limit_usd_column: int | None = None,
        actual_usd_column: int | None = None, free_limit_usd_column: int | None = None,
        signal_raw_column: int | None = None, base_label_column: int | None = None,
    ) -> None:
        label_text = _text(_cell(row, label_column))
        if not label_text:
            issues.append(_issue("RISK-02", "medium", f"Строка в разделе «{dimension}» не удалось классифицировать", (dimension,), sheet_name, row_number))
            return
        limit_pct, limit_kzt = _cell(row, limit_pct_column), _cell(row, limit_kzt_column)
        actual_pct, actual_kzt = _cell(row, actual_pct_column), _cell(row, actual_kzt_column)
        free_limit_kzt = _cell(row, free_limit_kzt_column)
        limit_usd, actual_usd, free_limit_usd = _cell(row, limit_usd_column), _cell(row, actual_usd_column), _cell(row, free_limit_usd_column)
        signal_raw, base_label = _cell(row, signal_raw_column), _cell(row, base_label_column)
        signal = _risk_signal(signal_raw, limit_kzt, actual_kzt, limit_usd, actual_usd)
        if signal is None:
            issues.append(_issue("RISK-01", "medium", f"Не удалось определить статус лимита для «{label_text}»", ("signal",), sheet_name, row_number))
        utilization = _risk_utilization(limit_pct, actual_pct, limit_kzt, actual_kzt, limit_usd, actual_usd, base_label)
        payload = {
            "dimension": dimension, "label": label_text,
            "limit_pct": _decimal_text(limit_pct), "limit_kzt": _decimal_text(limit_kzt),
            "actual_pct": _decimal_text(actual_pct), "actual_kzt": _decimal_text(actual_kzt),
            "free_limit_kzt": _decimal_text(free_limit_kzt),
            "limit_usd": _decimal_text(limit_usd), "actual_usd": _decimal_text(actual_usd),
            "free_limit_usd": _decimal_text(free_limit_usd),
            "signal": signal, "base_label": _text(base_label) or None, "portfolio_code": scope,
            "utilization": _decimal_text(utilization),
            "near_breach": _risk_near_breach(signal, utilization),
            "near_breach_threshold": str(RISK_NEAR_BREACH_THRESHOLD),
            "near_breach_policy_version": RISK_NEAR_BREACH_POLICY_VERSION,
        }
        record_key = hashlib.sha256(f"{dimension}|{_normalize_name(label_text)}|{scope}".encode()).hexdigest()[:24]
        field_columns = {
            "limit_pct": limit_pct_column, "limit_kzt": limit_kzt_column,
            "actual_pct": actual_pct_column, "actual_kzt": actual_kzt_column,
            "free_limit_kzt": free_limit_kzt_column, "limit_usd": limit_usd_column,
            "actual_usd": actual_usd_column, "free_limit_usd": free_limit_usd_column,
        }
        records.append(_record("risk_limit", record_key, payload, sheet_name, row_number, column=label_column, field_columns=field_columns))

    sheet_name = "Лимиты"
    limits_rows = workbook.get_sheet_by_name(sheet_name).to_python(skip_empty_area=False)
    limits_columns = _rows_header_columns(limits_rows, _RISK_LIMITS_ALIASES, max_row=6)
    if set(_RISK_LIMITS_ALIASES) - set(limits_columns):
        issues.append(_issue("RISK-MAP-01", "high", "Не удалось однозначно сопоставить столбцы раздела «Лимиты»: " + ", ".join(sorted(set(_RISK_LIMITS_ALIASES) - set(limits_columns))), tuple(sorted(set(_RISK_LIMITS_ALIASES) - set(limits_columns))), sheet_name, 4))
    for row_number, row in enumerate(limits_rows, 1):
        if len(row) < 9:
            continue
        marker = row[1]
        if isinstance(marker, bool) or not isinstance(marker, (int, float)):
            continue
        add_record(
            "instrument_category", sheet_name=sheet_name, row_number=row_number, row=row,
            label_column=limits_columns.get("label"), limit_kzt_column=limits_columns.get("limit_kzt"),
            actual_pct_column=limits_columns.get("actual_pct"), actual_kzt_column=limits_columns.get("actual_kzt"),
            free_limit_kzt_column=limits_columns.get("free_limit_kzt"),
        )

    sheet_name = "Лимит по странам"
    country_rows = workbook.get_sheet_by_name(sheet_name).to_python(skip_empty_area=False)
    country_columns = _rows_header_columns(country_rows, _RISK_COUNTRY_ALIASES, max_row=4)
    if set(_RISK_COUNTRY_ALIASES) - set(country_columns):
        issues.append(_issue("RISK-MAP-02", "high", "Не удалось однозначно сопоставить столбцы раздела «Лимит по странам»: " + ", ".join(sorted(set(_RISK_COUNTRY_ALIASES) - set(country_columns))), tuple(sorted(set(_RISK_COUNTRY_ALIASES) - set(country_columns))), sheet_name, 3))
    for row_number, row in enumerate(country_rows, 1):
        if len(row) < 21:
            continue
        marker = row[1]
        if isinstance(marker, bool) or not isinstance(marker, (int, float)):
            continue
        add_record(
            "country", sheet_name=sheet_name, row_number=row_number, row=row,
            label_column=country_columns.get("label"), limit_kzt_column=country_columns.get("limit_kzt"),
            limit_usd_column=country_columns.get("limit_usd"), actual_usd_column=country_columns.get("actual_usd"),
            free_limit_usd_column=country_columns.get("free_limit_usd"),
        )

    # "Лимиты" и "Лимит по странам" (above) are the two sheets detection
    # itself requires, so they're safe to open unconditionally here - if
    # either were missing, this function would never have been called.
    # Эмитента/Отрасль/МСФО are optional dimensions the same way Лимит по
    # дюрации/Расшифровка/Detail below already are (each independently
    # present or absent in a real workbook) - guard them the same way,
    # instead of a bare get_sheet_by_name that raises WorksheetNotFound and
    # fails the entire "limits" dataset over one missing optional sheet.
    sheet_name = "Лимит на Эмитента"
    if sheet_name in workbook.sheet_names:
        issuer_rows = workbook.get_sheet_by_name(sheet_name).to_python(skip_empty_area=False)
        issuer_columns = _rows_header_columns(issuer_rows, _RISK_ISSUER_OR_SECTOR_ALIASES, max_row=6)
        if "label" not in issuer_columns:
            issues.append(_issue("RISK-MAP-03", "high", "Не удалось найти столбец наименования в разделе «Лимит на Эмитента»", ("label",), sheet_name, 5))
        issuer_label_column = issuer_columns.get("label")
        for row_number, row in enumerate(issuer_rows, 1):
            if row_number <= 5 or len(row) < 11:
                continue
            label = _text(_cell(row, issuer_label_column))
            if not label or label.casefold().startswith("итого"):
                continue
            add_record(
                "issuer", sheet_name=sheet_name, row_number=row_number, row=row,
                label_column=issuer_label_column, actual_kzt_column=issuer_columns.get("actual_kzt"),
                limit_kzt_column=issuer_columns.get("limit_kzt"), actual_pct_column=issuer_columns.get("actual_pct"),
                limit_pct_column=issuer_columns.get("limit_pct"), free_limit_kzt_column=issuer_columns.get("free_limit_kzt"),
                signal_raw_column=issuer_columns.get("signal_raw"), base_label_column=issuer_columns.get("base_label"),
            )

    sheet_name = "Лимит на Отрасль"
    if sheet_name in workbook.sheet_names:
        seen_total = False
        sector_rows = workbook.get_sheet_by_name(sheet_name).to_python(skip_empty_area=False)
        sector_columns = _rows_header_columns(sector_rows, _RISK_ISSUER_OR_SECTOR_ALIASES, max_row=6)
        if "label" not in sector_columns:
            issues.append(_issue("RISK-MAP-04", "high", "Не удалось найти столбец наименования в разделе «Лимит на Отрасль»", ("label",), sheet_name, 5))
        sector_label_column = sector_columns.get("label")
        for row_number, row in enumerate(sector_rows, 1):
            if len(row) < 5:
                continue
            label = _text(_cell(row, sector_label_column))
            if label.casefold().startswith("итого"):
                seen_total = True
                continue
            if not seen_total or not label:
                continue
            add_record(
                "sector", sheet_name=sheet_name, row_number=row_number, row=row,
                label_column=sector_label_column, actual_kzt_column=sector_columns.get("actual_kzt"),
                actual_pct_column=sector_columns.get("actual_pct"),
            )

    sheet_name = "Лимит по МСФО"
    if sheet_name in workbook.sheet_names:
        ifrs_rows = workbook.get_sheet_by_name(sheet_name).to_python(skip_empty_area=False)
        ifrs_columns = _rows_header_columns(ifrs_rows, _RISK_IFRS_ALIASES, max_row=6)
        if set(_RISK_IFRS_ALIASES) - set(ifrs_columns):
            issues.append(_issue("RISK-MAP-05", "high", "Не удалось однозначно сопоставить столбцы раздела «Лимит по МСФО»: " + ", ".join(sorted(set(_RISK_IFRS_ALIASES) - set(ifrs_columns))), tuple(sorted(set(_RISK_IFRS_ALIASES) - set(ifrs_columns))), sheet_name, 3))
        for row_number, row in enumerate(ifrs_rows, 1):
            if len(row) < 8:
                continue
            marker = row[1]
            if isinstance(marker, bool) or not isinstance(marker, (int, float)):
                continue
            add_record(
                "ifrs", sheet_name=sheet_name, row_number=row_number, row=row,
                label_column=ifrs_columns.get("label"), limit_pct_column=ifrs_columns.get("limit_pct"),
                limit_kzt_column=ifrs_columns.get("limit_kzt"), actual_pct_column=ifrs_columns.get("actual_pct"),
                actual_kzt_column=ifrs_columns.get("actual_kzt"), free_limit_kzt_column=ifrs_columns.get("free_limit_kzt"),
            )

    # Duration is a separate control in the workbook: it has no currency limit
    # but compares each instrument's modified duration with a maximum duration.
    duration_count = 0
    duration_breaches = 0
    if "Лимит по дюрации" in workbook.sheet_names:
        duration_rows = workbook.get_sheet_by_name("Лимит по дюрации").to_python(skip_empty_area=False)
        duration_columns = _rows_header_columns(duration_rows, _RISK_DURATION_ALIASES, max_row=4)
        required_duration = ("duration_limit", "modified_duration", "isin")
        if [field for field in required_duration if field not in duration_columns]:
            issues.append(_issue(
                "RISK-MAP-06", "high",
                "Не удалось однозначно сопоставить столбцы раздела «Лимит по дюрации»: "
                + ", ".join(sorted(set(required_duration) - set(duration_columns))),
                tuple(sorted(set(required_duration) - set(duration_columns))), "Лимит по дюрации", 3,
            ))
        isin_column = duration_columns.get("isin")
        for row_number, row in enumerate(duration_rows, 1):
            if row_number <= 3 or len(row) < 16 or not _text(_cell(row, isin_column)):
                continue
            limit_duration, modified_duration = _cell(row, duration_columns.get("duration_limit")), _cell(row, duration_columns.get("modified_duration"))
            signal = _risk_signal(None, limit_duration, modified_duration)
            issuer_column = duration_columns.get("issuer")
            duration_label_column = issuer_column if issuer_column is not None and _text(_cell(row, issuer_column)) else duration_columns.get("label_alt")
            duration_label = _text(_cell(row, duration_label_column))
            if signal is None:
                issues.append(_issue("RISK-01", "medium", f"Не удалось определить статус дюрации для «{duration_label}»", ("signal",), "Лимит по дюрации", row_number))
            try:
                headroom = Decimal(str(limit_duration)) - Decimal(str(modified_duration))
            except (InvalidOperation, ValueError, TypeError):
                headroom = None
            payload = {
                "dimension": "duration", "label": duration_label,
                "duration_limit": _decimal_text(limit_duration),
                "modified_duration": _decimal_text(modified_duration),
                "duration_headroom": _decimal_text(headroom),
                "resident_status": _text(_cell(row, duration_columns.get("resident_status"))), "country": _text(_cell(row, duration_columns.get("country"))),
                "sector_gics": _text(_cell(row, duration_columns.get("sector_gics"))), "currency": _text(_cell(row, duration_columns.get("currency"))),
                "instrument_type": _text(_cell(row, duration_columns.get("instrument_type"))), "credit_rating": _text(_cell(row, duration_columns.get("credit_rating"))),
                "ifrs_method": _text(_cell(row, duration_columns.get("ifrs_method"))), "trading_code": _text(_cell(row, duration_columns.get("trading_code"))),
                "isin": _text(_cell(row, isin_column)), "issuer": _text(_cell(row, issuer_column)),
                "carrying_value_native": _decimal_text(_cell(row, duration_columns.get("carrying_value_native"))),
                "carrying_value_kzt": _decimal_text(_cell(row, duration_columns.get("carrying_value_kzt"))),
                "weight_pct": _decimal_text(_cell(row, duration_columns.get("weight_pct"))), "coupon_pct": _decimal_text(_cell(row, duration_columns.get("coupon_pct"))),
                "ytm_purchase_pct": _decimal_text(_cell(row, duration_columns.get("ytm_purchase_pct"))), "ytm_report_pct": _decimal_text(_cell(row, duration_columns.get("ytm_report_pct"))),
                "maturity_date": _date_text(_cell(row, duration_columns.get("maturity_date"))), "signal": signal, "portfolio_code": scope,
            }
            duration_field_columns = {
                "duration_limit": duration_columns.get("duration_limit"), "modified_duration": duration_columns.get("modified_duration"),
                "carrying_value_native": duration_columns.get("carrying_value_native"),
                "carrying_value_kzt": duration_columns.get("carrying_value_kzt"), "isin": isin_column, "issuer": issuer_column,
            }
            records.append(_record("risk_limit", f"duration:{row_number}", payload, "Лимит по дюрации", row_number, column=duration_label_column, field_columns=duration_field_columns))
            duration_count += 1
            duration_breaches += int(signal == "breach")

    # Расшифровка is the workbook's currency/instrument exposure evidence.
    exposure_count = 0
    exposure_by_currency: dict[str, Decimal] = {}
    if "Расшифровка" in workbook.sheet_names:
        exposure_rows = workbook.get_sheet_by_name("Расшифровка").to_python(skip_empty_area=False)
        exposure_columns = _rows_header_columns(exposure_rows, _RISK_EXPOSURE_ALIASES, max_row=2)
        if set(_RISK_EXPOSURE_ALIASES) - set(exposure_columns):
            issues.append(_issue(
                "RISK-MAP-07", "high",
                "Не удалось однозначно сопоставить столбцы раздела «Расшифровка»: "
                + ", ".join(sorted(set(_RISK_EXPOSURE_ALIASES) - set(exposure_columns))),
                tuple(sorted(set(_RISK_EXPOSURE_ALIASES) - set(exposure_columns))), "Расшифровка", 1,
            ))
        instrument_group_column = exposure_columns.get("instrument_group")
        # "ФИ" (the label column's own header) is too short/generic a string to
        # safely label-match - it risks matching unrelated headers elsewhere by
        # substring. It sits immediately right of "Тип инструмента" by the
        # workbook's own convention, so derive it from that resolved column
        # instead of a hardcoded literal.
        exposure_label_column = instrument_group_column + 1 if instrument_group_column is not None else None
        currency_column, amount_native_column = exposure_columns.get("currency"), exposure_columns.get("amount_native")
        fx_rate_column, amount_kzt_column = exposure_columns.get("fx_rate"), exposure_columns.get("amount_kzt")
        for row_number, row in enumerate(exposure_rows, 1):
            if row_number == 1 or len(row) < 8 or not _text(_cell(row, exposure_label_column)):
                continue
            currency = _text(_cell(row, currency_column)) or "Не указано"
            amount_kzt = _d(_cell(row, amount_kzt_column))
            exposure_by_currency[currency] = exposure_by_currency.get(currency, Decimal("0")) + amount_kzt
            records.append(_record("risk_exposure", f"exposure:{row_number}", {
                "dimension": "exposure_detail", "label": _text(_cell(row, exposure_label_column)),
                "instrument_group": _text(_cell(row, instrument_group_column)), "currency": currency,
                "amount_native": _decimal_text(_cell(row, amount_native_column)), "fx_rate": _decimal_text(_cell(row, fx_rate_column)),
                "amount_kzt": _decimal_text(_cell(row, amount_kzt_column)), "portfolio_code": scope,
            }, "Расшифровка", row_number, column=exposure_label_column, field_columns={
                "instrument_group": instrument_group_column, "currency": currency_column,
                "amount_native": amount_native_column, "fx_rate": fx_rate_column, "amount_kzt": amount_kzt_column,
            }))
            exposure_count += 1

    # Detail is a country x instrument-category pivot: a country/currency
    # header row, followed by 4 fixed category subtotal rows (money/repo/
    # deposits, bonds, equities, other instruments), each optionally followed
    # by individual position lines that decompose that subtotal. Only the
    # subtotals are ingested here - the position lines are the same
    # information at finer grain than this control set needs, and most
    # countries have none (all-zero exposure). Row shape alone tells the
    # three kinds apart: a country header has a 3-letter currency code in
    # column 4; a category subtotal has a text label in column 1 and a
    # number in column 4; a position line has a number in column 1 instead.
    detail_rows = (
        workbook.get_sheet_by_name("Detail").to_python(skip_empty_area=False)
        if "Detail" in workbook.sheet_names else []
    )
    country_detail_count = 0
    current_country: str | None = None
    current_currency: str | None = None
    for row_number, row in enumerate(detail_rows, 1):
        if len(row) < 4:
            continue
        label, amount = row[0], row[3]
        if isinstance(label, str) and label.strip() and isinstance(amount, str) and re.fullmatch(r"[A-Z]{3}", amount.strip()):
            current_country, current_currency = label.strip(), amount.strip()
            continue
        if isinstance(label, str) and label.strip() and isinstance(amount, (int, float)) and current_country:
            records.append(_record("risk_country_detail", f"country_detail:{row_number}", {
                "dimension": "country_instrument_detail", "label": f"{current_country}: {label.strip()}",
                "country": current_country, "currency": current_currency, "instrument_category": label.strip(),
                "amount_native": _decimal_text(amount), "portfolio_code": scope,
            }, "Detail", row_number, column=3))
            country_detail_count += 1

    result = ParsedDataset("risk_limits_sobstv", "limits", "business_domain", scope, business_date, business_date, records=records, issues=issues)
    result.summary = _risk_summary(records)
    result.summary.update({
        "duration_count": duration_count, "duration_breach_count": duration_breaches,
        "exposure_detail_count": exposure_count,
        "exposure_by_currency": {key: _decimal_text(value) for key, value in sorted(exposure_by_currency.items())},
        "country_detail_count": country_detail_count,
    })
    return result


_TABYS_RISK_SECTION_DIMENSIONS = {
    "по стране": "country",
    "по валюте": "currency",
    "по эмитенту": "issuer",
    "по виду финансового инструмента": "instrument_category",
    "по gics отраслям": "sector",
    "по открытой валютной позиции": "fx_position",
    "по виду финансового инструмента одного эмитента": "instrument_issuer",
}


def _parse_risk_tabys(path: Path, scope: str) -> ParsedDataset:
    """Unified risk-limit lines for the TABYS fund.

    A single sheet ("Пр2-16") holds seven business "По ..." sections. All
    seven are extracted, including currency, open-FX, and instrument-per-
    issuer controls. TABYS has no IFRS breakdown, so it contributes zero
    `ifrs` rows.

    Each section carries its own subtotal row (blank label, so it's skipped
    below rather than ingested as a control). That subtotal legitimately runs
    a little over 100% - e.g. 100.0669% at the 2026-06-30 report - and this
    is not a data-quality gap: the source's "% of assets" columns use net
    assets (NAV) as the fixed denominator on every row, while the values
    summed across a fully-partitioning dimension (every country, or every
    currency) are gross position values. Since NAV = gross assets minus
    liabilities, Σ(actual_kzt) across such a dimension equals NAV +
    liabilities, so the total is always over 100% by exactly
    liabilities / NAV. No total-to-line tie-out is needed or meaningful here.
    """
    from osip_dashboard.ingestion import multi_source as _multi_source

    workbook = _multi_source.CalamineWorkbook.from_path(path)
    sheet_name = "Пр2-16"
    rows = workbook.get_sheet_by_name(sheet_name).to_python(skip_empty_area=False)
    business_date = _period_end_ddmmyy(_text(rows[3][1])) if len(rows) > 3 and len(rows[3]) > 1 else None
    records: list[dict[str, Any]] = []
    issues: list[ParsedIssue] = []
    columns = _rows_header_columns(rows, _RISK_TABYS_ALIASES, max_row=10)
    if set(_RISK_TABYS_ALIASES) - set(columns):
        issues.append(_issue(
            "RISK-MAP-08", "high",
            "Не удалось однозначно сопоставить столбцы раздела «По лимитам инвестирования»: "
            + ", ".join(sorted(set(_RISK_TABYS_ALIASES) - set(columns))),
            tuple(sorted(set(_RISK_TABYS_ALIASES) - set(columns))), sheet_name, 7,
        ))
    label_column = columns.get("label")
    limit_pct_column, actual_pct_column = columns.get("limit_pct"), columns.get("actual_pct")
    limit_kzt_column, actual_kzt_column, signal_raw_column = columns.get("limit_kzt"), columns.get("actual_kzt"), columns.get("signal_raw")
    current_dimension: str | None = None
    for row_number, row in enumerate(rows, 1):
        if len(row) < 7:
            continue
        label = _text(_cell(row, label_column))
        if not label:
            continue
        if label.startswith("##md"):
            # Template placeholders at the bottom of the TABYS sheet are not
            # business rows and must not become unresolved controls.
            continue
        folded = label.casefold()
        if folded.startswith("по "):
            current_dimension = _TABYS_RISK_SECTION_DIMENSIONS.get(folded)
            continue
        if current_dimension is None:
            continue
        limit_pct, actual_pct = _cell(row, limit_pct_column), _cell(row, actual_pct_column)
        limit_kzt, actual_kzt, signal_raw = _cell(row, limit_kzt_column), _cell(row, actual_kzt_column), _cell(row, signal_raw_column)
        free_limit_kzt = None
        if limit_kzt not in (None, "") and actual_kzt not in (None, ""):
            try:
                free_limit_kzt = Decimal(str(limit_kzt)) - Decimal(str(actual_kzt))
            except (InvalidOperation, ValueError):
                free_limit_kzt = None
        signal = _risk_signal(signal_raw, limit_kzt, actual_kzt)
        if signal is None:
            issues.append(_issue("RISK-01", "medium", f"Не удалось определить статус лимита для «{label}»", ("signal",), sheet_name, row_number))
        utilization = _risk_utilization(limit_pct, actual_pct, limit_kzt, actual_kzt)
        payload = {
            "dimension": current_dimension, "label": label,
            "limit_pct": _decimal_text(limit_pct), "limit_kzt": _decimal_text(limit_kzt),
            "actual_pct": _decimal_text(actual_pct), "actual_kzt": _decimal_text(actual_kzt),
            "free_limit_kzt": _decimal_text(free_limit_kzt),
            "limit_usd": None, "actual_usd": None, "free_limit_usd": None,
            "signal": signal, "base_label": None, "portfolio_code": scope,
            "utilization": _decimal_text(utilization),
            "near_breach": _risk_near_breach(signal, utilization),
            "near_breach_threshold": str(RISK_NEAR_BREACH_THRESHOLD),
            "near_breach_policy_version": RISK_NEAR_BREACH_POLICY_VERSION,
        }
        record_key = hashlib.sha256(f"{current_dimension}|{_normalize_name(label)}|{scope}".encode()).hexdigest()[:24]
        records.append(_record("risk_limit", record_key, payload, sheet_name, row_number, column=label_column, field_columns={
            "limit_pct": limit_pct_column, "actual_pct": actual_pct_column, "limit_kzt": limit_kzt_column, "actual_kzt": actual_kzt_column,
        }))
    result = ParsedDataset("risk_limits_tabys", "limits", "business_domain", scope, business_date, business_date, records=records, issues=issues)
    result.summary = _risk_summary(records)
    return result


def _risk_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    detail_dimensions = {"exposure_detail", "country_instrument_detail"}
    controls = [item for item in records if item.get("payload", {}).get("dimension") not in detail_dimensions]
    signal_counts: dict[str, int] = {}
    dimension_counts: dict[str, int] = {}
    near_breach_count = 0
    for item in records:
        payload = item.get("payload", {})
        dimension = str(payload.get("dimension") or "unknown")
        dimension_counts[dimension] = dimension_counts.get(dimension, 0) + 1
        if dimension in detail_dimensions:
            continue
        signal = str(payload.get("signal") or "unknown")
        signal_counts[signal] = signal_counts.get(signal, 0) + 1
        if payload.get("near_breach"):
            near_breach_count += 1
    return {
        "record_count": len(records),
        "limit_count": len(controls),
        "detail_count": len(records) - len(controls),
        "breach_count": signal_counts.get("breach", 0),
        "near_breach_count": near_breach_count,
        "near_breach_threshold": str(RISK_NEAR_BREACH_THRESHOLD),
        "near_breach_policy_version": RISK_NEAR_BREACH_POLICY_VERSION,
        "unknown_count": signal_counts.get("unknown", 0),
        "not_applicable_count": signal_counts.get("not_applicable", 0),
        "signal_counts": signal_counts,
        "dimension_counts": dimension_counts,
    }
