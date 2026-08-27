import { getCurrentLanguage, translate, type AppLanguage } from "../i18n";

function locale(language: AppLanguage) {
  return language === "en" ? "en-GB" : "ru-RU";
}

export function formatKzt(value: string | number | null | undefined, language = getCurrentLanguage()): string {
  if (value === null || value === undefined) return translate(language, "common.unavailable");
  const formatted = new Intl.NumberFormat(locale(language), { maximumFractionDigits: 0 }).format(Number(value));
  // The tenge symbol alone (not the "KZT" text) in both languages - a text
  // prefix made the English KPI cards wrap onto their own line for large
  // sums, since it added width the symbol-only Russian form didn't have.
  return `${formatted} ₸`;
}

export function formatPercent(value: string | number | null | undefined, maximumFractionDigits = 1, language = getCurrentLanguage()): string {
  if (value === null || value === undefined) return translate(language, "common.unavailable");
  return `${new Intl.NumberFormat(locale(language), { maximumFractionDigits }).format(Number(value))}%`;
}

export function formatNumber(
  value: string | number | null | undefined,
  language = getCurrentLanguage(),
  maximumFractionDigits = 4
): string {
  if (value === null || value === undefined) return translate(language, "common.unavailable");
  return new Intl.NumberFormat(locale(language), { maximumFractionDigits }).format(Number(value));
}

export function formatDate(value: string | null | undefined, language = getCurrentLanguage()): string {
  // A missing date is independent from workflow publication.  In particular,
  // a published landing dataset may legitimately have no business date.
  if (!value) return translate(language, "common.unavailable");
  return new Intl.DateTimeFormat(locale(language), {
    day: "2-digit",
    month: "short",
    year: "numeric"
  }).format(new Date(`${value}T00:00:00`));
}

export function formatReportDate(value: string | null | undefined, language = getCurrentLanguage()): string {
  if (!value) return translate(language, "common.noPublication");
  return new Intl.DateTimeFormat(locale(language), language === "en"
    ? { day: "2-digit", month: "short", year: "numeric" }
    : { day: "2-digit", month: "2-digit", year: "numeric" }
  ).format(new Date(`${value}T00:00:00`));
}

const labels: Record<string, { ru: string; en: string }> = {
  date_mismatch: { ru: "Несовпадение дат", en: "Date mismatch" }, pass: { ru: "Сверено", en: "Pass" }, fail: { ru: "Не сходится", en: "Fail" }, ok: { ru: "В пределах лимита", en: "Within limit" }, breach: { ru: "Превышение лимита", en: "Breach" }, near_breach: { ru: "Близко к превышению", en: "Near-breach" }, warning: { ru: "Требует внимания", en: "Needs attention" }, unknown: { ru: "Статус не определён", en: "Status unknown" }, not_applicable: { ru: "Без применимого лимита", en: "No applicable limit" }, fresh: { ru: "Свежий", en: "Fresh" }, aging: { ru: "Требует внимания", en: "Aging" }, stale: { ru: "Устарело", en: "Stale" }, future: { ru: "Дата в будущем", en: "Future date" }, unavailable: { ru: "Недоступно", en: "Unavailable" },
  ready: { ru: "Готово", en: "Ready" }, due: { ru: "Требует обновления", en: "Due" }, blocked: { ru: "Заблокировано DQ", en: "Blocked by DQ" }, missing: { ru: "Не загружено", en: "Not uploaded" },
  asset_class: { ru: "Класс актива", en: "Asset class" }, approved: { ru: "Утверждено", en: "Approved" }, blocker: { ru: "Блокирующее", en: "Blocker" }, cash: { ru: "Денежные средства", en: "Cash" }, coupon: { ru: "Купон", en: "Coupon" }, derived_carrying: { ru: "Расчётная балансовая стоимость", en: "Derived carrying value" }, draft: { ru: "Черновик", en: "Draft" }, failed: { ru: "Ошибка", en: "Failed" }, high: { ru: "Высокая", en: "High" }, historical: { ru: "Прошедшее", en: "Historical" }, low: { ru: "Низкая", en: "Low" }, medium: { ru: "Средняя", en: "Medium" }, maturity: { ru: "Погашение", en: "Maturity" }, overdue: { ru: "Просрочено", en: "Overdue" }, published: { ru: "Опубликовано", en: "Published" }, rejected: { ru: "Отклонено", en: "Rejected" }, repo: { ru: "РЕПО", en: "Repo" }, settlement: { ru: "Расчёт", en: "Settlement" }, instrument_open: { ru: "Покупка / открытие", en: "Instrument opened" }, repo_open: { ru: "Открытие РЕПО", en: "Repo opened" }, repo_close: { ru: "Закрытие РЕПО", en: "Repo closed" }, previous_coupon: { ru: "Предыдущий купон", en: "Previous coupon" }, next_coupon: { ru: "Следующий купон", en: "Next coupon" }, source_purchase_amount: { ru: "Источник: сумма покупки", en: "Source: purchase amount" }, source: { ru: "Источник", en: "Source" }, superseded: { ru: "Заменено", en: "Superseded" }, upcoming: { ru: "Предстоящее", en: "Upcoming" }, withdrawn: { ru: "Снято с публикации", en: "Withdrawn" }, validated: { ru: "Проверено", en: "Validated" }, validating: { ru: "Проверка", en: "Validating" }, version: { ru: "Версия", en: "Version" }, not_supplied: { ru: "Не указано", en: "Not supplied" }, purchase_amount_kzt: { ru: "Сумма покупки", en: "Purchase amount" }, derived_carrying_value_kzt: { ru: "Расчётная балансовая стоимость", en: "Derived carrying value" }, independent_approval: { ru: "Независимое утверждение", en: "Independent approval" }, critical_dq_acknowledged: { ru: "Критические DQ подтверждены", en: "Critical DQ acknowledged" }, carrying_price: { ru: "Цена балансовой стоимости", en: "Carrying price" }, official_carrying_value_kzt: { ru: "Официальная балансовая стоимость", en: "Official carrying value" }, official_market_value_kzt: { ru: "Официальная рыночная стоимость", en: "Official market value" }, days_held: { ru: "Дней в портфеле", en: "Days held" }, portfolio_weight: { ru: "Доля в портфеле", en: "Portfolio weight" }, income: { ru: "Доход", en: "Income" }, holding_period_yield: { ru: "Доходность за период владения", en: "Holding period yield" }, expected_coupon: { ru: "Ожидаемый купон", en: "Expected coupon" }, settlement_date: { ru: "Дата расчёта", en: "Settlement date" }, status: { ru: "Статус", en: "Status" }, portfolio_id: { ru: "ID портфеля", en: "Portfolio ID" }, account_id: { ru: "ID счёта", en: "Account ID" }, lot_id: { ru: "ID лота", en: "Lot ID" }, transaction_id: { ru: "ID операции", en: "Transaction ID" }, settlement_id: { ru: "ID расчёта", en: "Settlement ID" }, price_source: { ru: "Источник цены", en: "Price source" }, valuation_timestamp: { ru: "Время оценки", en: "Valuation timestamp" }, raw_sector: { ru: "Исходный сектор", en: "Raw sector" }, normalized_sector: { ru: "Нормализованный сектор", en: "Normalized sector" }, listing_rating: { ru: "Листинговый рейтинг", en: "Listing rating" }, ratings: { ru: "Рейтинги", en: "Ratings" }, physical_sheet_dimensions: { ru: "Физические размеры листа", en: "Physical sheet dimensions" }
};

export function humanize(value: string, language = getCurrentLanguage()): string {
  return labels[value.toLowerCase()]?.[language] ?? value.replaceAll("_", " ");
}

const assetClassLabels: Record<string, { ru: string; en: string }> = {
  "Corporate bond": { ru: "Корпоративные облигации", en: "Corporate bonds" },
  "Government bond": { ru: "Государственные облигации", en: "Government bonds" },
  "Government bonds": { ru: "Государственные облигации", en: "Government bonds" },
  Equity: { ru: "Акции", en: "Equities" },
  ETF: { ru: "ETF", en: "ETF" },
  Repo: { ru: "РЕПО", en: "Repo" },
  "Development Institutions": { ru: "Институты развития", en: "Development institutions" },
  "Not supplied": { ru: "Не указано", en: "Not supplied" },
  Commodity: { ru: "Товары / сырьё", en: "Commodities" }
};

export function formatAssetClass(value: string, language = getCurrentLanguage()): string {
  return assetClassLabels[value]?.[language] ?? value;
}

const metricLabels: Record<string, { ru: string; en: string }> = {
  position_count: { ru: "Текущие лоты", en: "Current lots" },
  unique_isin_count: { ru: "Уникальные инструменты", en: "Unique instruments" },
  purchase_amount_kzt: { ru: "Сумма покупки", en: "Purchase amount" },
  derived_carrying_value_kzt: { ru: "Расчётная балансовая стоимость", en: "Derived carrying value" },
  cash_kzt: { ru: "Денежный эквивалент", en: "Cash equivalent" },
  derived_operational_total_kzt: { ru: "Операционный итог", en: "Derived operational total" },
  total_fees_kzt: { ru: "Комиссии организатора и брокера", en: "Organizer and broker fees" },
  total_reserves_kzt: { ru: "Учтённые резервы", en: "Reported reserves" },
  official_nav_kzt: { ru: "Официальный NAV", en: "Official NAV" },
  official_performance: { ru: "Официальная эффективность", en: "Official performance" }
};

export function formatMetricLabel(code: string, fallback: string, language = getCurrentLanguage()): string {
  return metricLabels[code]?.[language] ?? fallback;
}

const metricUnavailableReasons: Record<string, { ru: string; en: string }> = {
  official_nav_kzt: {
    ru: "Утверждённые цены, обязательства, денежные потоки, политика оценки и утверждение NAV недоступны.",
    en: "Approved prices, liabilities, cash flows, valuation policy, and NAV approval are unavailable."
  },
  official_performance: {
    ru: "Исторический NAV, внешние денежные потоки, данные бенчмарка и утверждённая методология недоступны.",
    en: "Historical NAV, external cash flows, benchmark data, and approved methodology are unavailable."
  }
};

export function formatMetricReason(code: string, fallback: string, language = getCurrentLanguage()): string {
  return metricUnavailableReasons[code]?.[language] ?? fallback;
}
