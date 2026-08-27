"""Small, reviewed locale catalogue for user-facing API text.

The API keeps codes, raw source evidence and financial values language-neutral.
Only deterministic application messages are localized from ``Accept-Language``.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request


_MESSAGES: dict[str, str] = {
    "Обязательные расчётные показатели рабочей книги недоступны.": "Required derived workbook metrics are unavailable.",
    "Расчёт остаётся в разделе предстоящих событий после наступления срока.": "A settlement remains in the upcoming-events section after its due date.",
    "В рабочей книге отсутствуют устойчивые идентификаторы портфеля, счёта, лота, операции или расчёта.": "The workbook does not contain stable identifiers for the portfolio, account, lot, transaction, or settlement.",
    "В рабочей книге нет источника цены и времени оценки, необходимых для подтверждения рыночной стоимости.": "The workbook has no price source or valuation timestamp required to substantiate market value.",
    "Портфель не найден": "Portfolio not found",
    "Снимок не найден": "Snapshot not found",
    "Нет доступа к загрузке": "You do not have access to this upload",
    "Сохранённый файл источника недоступен": "The stored source file is unavailable",
    "Артефакт отчёта не найден": "Report artifact not found",
    "Некорректная дата срока устранения": "Invalid remediation due date",
    "Выгрузка доступна только для опубликованной версии портфеля": "Export is available only for a published portfolio version",
    "Не удалось найти бизнес-заголовок OSIP по стабильному контракту столбцов": "Could not find the OSIP business header using the stable column contract",
    "Операционные/расчётные данные портфеля; не официальный NAV или рыночная стоимость.": "Operational/derived portfolio data; not official NAV or market value.",
    "Операционные/данные из источника; не утверждённый бухгалтерский NAV или показатель доходности.": "Operational/source-reported data; not an accounting-approved official NAV or performance measure.",
    "Ожидается источник по рискам; показатели VaR, лимитов, капитала и стресса не рассчитываются.": "Risk source pending; no VaR, limits, capital or stress metrics are calculated.",
    "Авторитетный бухгалтерский пакет": "Authoritative accounting package",
    "Период и единицы учёта": "Accounting period and units",
    "Проверка формул и внешних ссылок": "Formula and external-link review",
    "Независимое утверждение бухгалтерских метрик": "Independent approval of accounting metrics",
    "Текущие книги доступны только для landing/DQ; официальный набор ещё не подтверждён.": "Current workbooks are available for landing/DQ only; the authoritative package is not confirmed.",
    "Проверяются конфликты дат, названий и валют.": "Date, title, and currency conflicts are reviewed.",
    "Ошибки формул сохраняются как доказательство и не публикуются как нули.": "Formula errors are retained as evidence and are not published as zeros.",
    "Недоступно до получения полного источника и контракта показателей.": "Unavailable until the complete source and metric contract are provided.",
    "Позиции и идентификаторы экспозиций": "Exposure positions and identifiers",
    "Кривые, цены, волатильности и корреляции": "Curves, prices, volatilities, and correlations",
    "Капитал и ликвидность": "Capital and liquidity",
    "Лимиты, владельцы и политика": "Limits, owners, and policy",
    "Сценарии и версия модели": "Scenarios and model version",
    "Нужны счета, инструменты, валюты и количества.": "Accounts, instruments, currencies, and quantities are required.",
    "Без рыночных факторов VaR и чувствительности не рассчитываются.": "VaR and sensitivities cannot be calculated without market factors.",
    "Официальные регуляторные входы отсутствуют.": "Official regulatory inputs are unavailable.",
    "Нужны пороги, даты пересмотра и исключения.": "Thresholds, review dates, and exceptions are required.",
    "Стресс-расчёты будут доступны только с утверждённой методологией.": "Stress calculations require an approved methodology.",
    "Текст сектора в источнике смешивает сектора GICS, классы активов и списки нескольких секторов.": "The source sector text mixes GICS sectors, asset classes, and multi-sector lists.",
    "Заявленные размеры листа содержат большое число отформатированных пустых строк в конце.": "The sheet's declared dimensions include a large number of formatted blank rows at the end.",
    "Неверное имя пользователя или пароль": "Incorrect username or password",
    "Учётная запись временно заблокирована из-за неудачных попыток входа. Повторите попытку позже.": "This account is temporarily locked after repeated failed sign-in attempts. Try again later.",
    "Демо-вход не включён": "Demo sign-in is not enabled",
    "Токен сессии недействителен": "Session token is invalid",
    "Требуется Bearer-токен": "A Bearer token is required",
    "Идентификатор в Bearer-токене недействителен": "The identifier in the Bearer token is invalid",
    "Адрес ячейки должен иметь формат A1": "The cell address must be in A1 format",
}

# A handful of OSIP DQ findings (DQ-02, DQ-12) interpolate a count into the
# message, so they can never match the exact-string lookup above even after
# translating the static template - localize by code instead, same approach
# as the newer ingestion family's localize_dataset_issue().
_DQ_ISSUE_MESSAGES: dict[str, str] = {
    "DQ-02": "A settlement instruction appears more than once for the same trade.",
    "DQ-12": "Listing and ratings coverage is incomplete for one or more lots.",
}

_WORKFLOW: dict[str, tuple[str, str]] = {
    "snapshot_not_published": ("Снимок не опубликован.", "Snapshot is not published."),
    "independent_approval_missing": ("Отсутствует независимое утверждение проверяющего.", "Independent reviewer approval is missing."),
    "unacknowledged_dq": ("Неподтверждённые блокирующие/высокие коды DQ: {codes}", "Unacknowledged blocker/high DQ codes: {codes}"),
    "official_data_unavailable": ("Недоступны официальная оценка, NAV, методика доходности и авторитетные регистры.", "Official valuation, NAV, performance methodology, and authoritative ledgers are unavailable."),
    "settlement_amount_unavailable": ("Валюта суммы расчёта и его статус не являются авторитетными.", "Settlement amount currency and status are not authoritative."),
}

_DATASET_ISSUES: dict[str, str] = {
    "TABYS-NAV-01": "NAV does not equal securities plus cash minus liabilities.",
    "TABYS-NAV-02": "Unit value does not reconcile to NAV and units outstanding.",
    "TABYS-PRICE-01": "One or more prices are missing from the price register.",
    "TABYS-PRICE-02": "The latest price date is more than one day before the valuation date.",
    "TABYS-EVIDENCE-01": "Historical or template sections are retained as evidence and excluded from current valuation.",
    "TABYS-EVIDENCE-02": "An evidence-only section contains broken formulas or external references.",
    "UNIT-01": "The unit-value series contains duplicate dates.",
    "UNIT-02": "The unit-value series is not in chronological order.",
    "UNIT-03": "The SAQ series is stale and requires explicit approval before publication.",
    "UNIT-04": "NAV or unit value is missing from one or more observations.",
    "UNIT-05": "One or more unit-value changes above 25% require explanation.",
    "UNIT-06": "The series contains external workbook references.",
    "UNIT-07": "The series contains broken formula references.",
    "CLIENT-01": "Cash totals are missing for some clients.",
    "CLIENT-02": "The opening-date reference contains duplicate normalized names.",
    "CLIENT-03": "Some opening-date names have no exact match in the client source.",
    "CLIENT-04": "Some opening-date names have ambiguous exact matches.",
    "BROKERAGE-MAP-01": "Required trade-ledger columns could not be mapped unambiguously; turnover and execution metrics require confirmation.",
    "CORPFIN-01": "An amount or unit is ambiguous; the original text is retained.",
    "CORPFIN-02": "No ISIN was found for the deal.",
    "CORPFIN-03": "The commission rate is missing.",
    "ACCOUNTING-00": "The source is retained for landing controls only; financial metrics are not published.",
    "ACCOUNTING-01": "The sheet contains formula or value errors.",
    "ACCOUNTING-02": "Conflicting dates were found across titles and sheets.",
    "ACCOUNTING-03": "The sheet contains external workbook references.",
    "ACCOUNTING-04": "Formula-error and external-link scanning is unavailable for .xls sources; it only runs for .xlsx.",
    "RISK-01": "A limit line's OK/breach status could not be determined from the source.",
    "RISK-02": "A row in a recognized section did not match the expected shape and was skipped.",
    "CLIENT-DASH-01": "The client summary sheet does not match the Лист4 register total; both values are retained as source.",
    "DERIV-01": "ETF rows were excluded (not derivative instruments); these trades are already recorded in the trade ledger (Лист8) as ETF.",
    "ACCOUNTING-BS-01": "Assets do not equal the sum of liabilities and equity.",
    "ACCOUNTING-IS-01": "Income minus expenses does not equal net profit before tax.",
}


def request_language(request: Request) -> str:
    """Return the supported language selected by the client, defaulting safely to RU."""
    for part in request.headers.get("accept-language", "").split(","):
        if part.strip().lower().startswith("en"):
            return "en"
        if part.strip().lower().startswith("ru"):
            return "ru"
    return "ru"


def localize_text(value: str, language: str) -> str:
    return _MESSAGES.get(value, value) if language == "en" else value


def localize_dq_issue(code: str, message: str, language: str) -> str:
    """Localize an OSIP DataQualityIssue, falling back to code-keyed text for messages with an interpolated count."""
    if language == "en" and code in _DQ_ISSUE_MESSAGES:
        return _DQ_ISSUE_MESSAGES[code]
    return localize_text(message, language)


def localize_detail(detail: Any, language: str) -> Any:
    if isinstance(detail, str):
        return localize_text(detail, language)
    if isinstance(detail, dict):
        return {key: localize_detail(value, language) for key, value in detail.items()}
    if isinstance(detail, list):
        return [localize_detail(value, language) for value in detail]
    return detail


def workflow_message(key: str, language: str, **values: object) -> str:
    ru, en = _WORKFLOW[key]
    return (en if language == "en" else ru).format(**values)


def localize_dataset_issue(code: str, message: str, language: str) -> str:
    return _DATASET_ISSUES.get(code, message) if language == "en" else message
