import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight } from "lucide-react";
import { dashboardApi } from "../../api/client";
import type { ModuleReadResponse } from "../../api/types";
import { EmptyState } from "../../components/ui/AsyncState";
import { Panel } from "../../components/ui/Panel";
import { SourceRowLegend } from "../../components/ui/SourceRowLegend";
import { StatusPill } from "../../components/ui/StatusPill";
import { TableSearch } from "../../components/ui/TableSearch";
import { formatDate, formatKzt } from "../../lib/format";
import { useScrollAnchor } from "../../hooks/useScrollAnchor";
import { ACCOUNTING_DATASET_TYPE_LABELS, DatasetVersionPicker, displayValue, SourceCell, STANDARD_TABLE_PAGE_SIZE, type Row } from "./shared";

export type IncomeStatementPeriod = "quarter" | "ytd";

// Only "Квартал"/"YTD" - the income statement source workbook carries
// exactly these two columns per line (quarter_kzt/ytd_kzt), plus their
// prior-year counterparts. There is no monthly column anywhere in this
// dataset, and "Год" isn't a distinct figure from YTD (YTD *is* the
// year-to-date total) - a Month or Year option here would have nothing
// real to switch to.
export function AccountingPeriodToggle({ value, onChange, language }: { value: IncomeStatementPeriod; onChange: (value: IncomeStatementPeriod) => void; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  return <label className="topbar-period-picker" title={l("Отчёт о прибылях и убытках", "Income statement")}>
    <span className="sr-only">{l("Отчёт о прибылях и убытках", "Income statement")}</span>
    <select value={value} onChange={(event) => onChange(event.target.value as IncomeStatementPeriod)}>
      <option value="quarter">{l("За квартал", "Quarter")}</option>
      <option value="ytd">{l("С начала года (YTD)", "Year to date (YTD)")}</option>
    </select>
  </label>;
}

export function AccountingComparabilityNotice({ language }: { language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  return <div className="alert-banner alert-banner--info" role="note">
    <AlertTriangle aria-hidden="true" />
    <div><strong>{l("Бюджет и бухгалтерская отчётность показаны отдельно", "Budget and accounting are shown separately")}</strong><p>{l("Автоматическое отклонение «бюджет–факт» не рассчитывается: соответствие строк ещё не утверждено. Все значения ниже остаются исходными показателями своих рабочих книг.", "No automatic budget-versus-actual variance is calculated because line mappings have not been approved. The values below remain source measures from their respective workbooks.")}</p></div>
  </div>;
}

export function AccountingReconciliationBanner({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  // The reconciliation checks (assets = liabilities + equity; income -
  // expenses = net profit) run once, at ingestion time, against the
  // statement's own total lines - see ACCOUNTING-BS-01/ACCOUNTING-IS-01 in
  // ingestion/multi_source.py. Reading dq_blocker_count off the published
  // manifest keeps this banner in lockstep with that check instead of
  // re-deriving the same arithmetic a second time in the browser.
  const flagged = data.sources.filter((source) => ["accounting_balance_sheet", "accounting_income_statement"].includes(source.dataset_type) && source.dq_blocker_count > 0);
  if (!flagged.length) return null;
  return <div className="alert-banner alert-banner--warning"><AlertTriangle /><div><strong>{l("Отчётность не сходится", "Statements do not reconcile")}</strong><p>{l("Обнаружено блокирующее расхождение контроля (активы/обязательства/капитал или доходы/расходы/прибыль). Показатели сохранены как есть из источника.", "A blocking reconciliation mismatch was found (assets/liabilities/equity or income/expenses/profit). Values are retained exactly as reported by the source.")}</p></div></div>;
}

const ACCOUNTING_BUDGET_SECTION_LABELS: Record<string, [string, string]> = {
  income_statement: ["Бюджет: доходы и расходы", "Budget: income and expenses"],
  cash_flow: ["Бюджет: движение денежных средств", "Budget: cash flow"],
  balance: ["Бюджет: баланс", "Budget: balance"],
};

export function AccountingBudgetSectionPanel({ data, language, section }: { data: ModuleReadResponse; language: "ru" | "en"; section: "income_statement" | "cash_flow" | "balance" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const [page, setPage] = useState(0);
  const pagination = useScrollAnchor<HTMLDivElement>();
  const allRecords = ((data.records as Record<string, Row[]>).accounting_budget ?? []);
  const records = allRecords.filter((row) => row.section === section);
  const pageSize = STANDARD_TABLE_PAGE_SIZE;
  const pageCount = Math.max(1, Math.ceil(records.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const visibleRows = records.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  const [titleRu, titleEn] = ACCOUNTING_BUDGET_SECTION_LABELS[section];
  return <Panel title={l(titleRu, titleEn)} subtitle={l(`Показано ${visibleRows.length} из ${records.length} строк; годы 2023-2025 и прогноз 2025, без данных за 2026 год - именно то, что содержит источник. Каждая строка сохраняет ссылку на исходную рабочую книгу.`, `${visibleRows.length} of ${records.length} rows shown; 2023-2025 and a 2025 forecast, no 2026 data - exactly what the source contains. Every row retains a source-workbook reference.`)} action={records.length ? <div className="table-tools"><TableSearch label={l("Поиск строк отчётности", "Search statement rows")} placeholder={l("Код, статья, раздел", "Code, line, section")} /><SourceRowLegend language={language} /></div> : undefined}>
    {records.length ? <><div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Статья", "Line")}</th><th>2023</th><th>2024</th><th>{l("Бюджет 9М 2025", "Budget 9M 2025")}</th><th>{l("Факт 9М 2025", "Actual 9M 2025")}</th><th>{l("Бюджет 2025", "Budget 2025")}</th><th>{l("Окт 2025", "Oct 2025")}</th><th>{l("Ноя 2025", "Nov 2025")}</th><th>{l("Дек 2025", "Dec 2025")}</th><th>{l("Прогноз 2025", "Forecast 2025")}</th><th>{l("% исполнения", "% execution")}</th><th>{l("Отклонение", "Deviation")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{visibleRows.map((row, index) => <tr key={String(row.id ?? index)}><td>{displayValue("line_label", row.line_label, language)}</td><td>{displayValue("year_2023_kzt", row.year_2023_kzt, language)}</td><td>{displayValue("year_2024_kzt", row.year_2024_kzt, language)}</td><td>{displayValue("budget_9m_2025_kzt", row.budget_9m_2025_kzt, language)}</td><td>{displayValue("actual_9m_2025_kzt", row.actual_9m_2025_kzt, language)}</td><td>{displayValue("budget_2025_kzt", row.budget_2025_kzt, language)}</td><td>{displayValue("oct_2025_kzt", row.oct_2025_kzt, language)}</td><td>{displayValue("nov_2025_kzt", row.nov_2025_kzt, language)}</td><td>{displayValue("dec_2025_kzt", row.dec_2025_kzt, language)}</td><td>{displayValue("forecast_2025_kzt", row.forecast_2025_kzt, language)}</td><td>{displayValue("execution_pct", row.execution_pct, language)}</td><td>{displayValue("deviation_kzt", row.deviation_kzt, language)}</td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div><div className="table-pagination" ref={pagination.ref}><span>{l(`Страница ${currentPage + 1} из ${pageCount} · ${pageSize} строк на странице`, `Page ${currentPage + 1} of ${pageCount} · ${pageSize} rows per page`)}</span><label className="table-pagination__jump"><span>{l("Перейти", "Go to")}</span><select aria-label={l("Выбрать страницу", "Choose page")} value={currentPage} onChange={(event) => { pagination.anchor(); setPage(Number(event.target.value)); }}>{Array.from({ length: pageCount }, (_, index) => <option key={index} value={index}>{index + 1}</option>)}</select></label><div><button className="icon-button" type="button" aria-label={l("Предыдущая страница", "Previous page")} disabled={currentPage === 0} onClick={() => { pagination.anchor(); setPage((value) => Math.max(0, value - 1)); }}><ChevronLeft aria-hidden="true" /></button><button className="icon-button" type="button" aria-label={l("Следующая страница", "Next page")} disabled={currentPage >= pageCount - 1} onClick={() => { pagination.anchor(); setPage((value) => Math.min(pageCount - 1, value + 1)); }}><ChevronRight aria-hidden="true" /></button></div></div></> : <EmptyState title={l("Нет данных в источнике", "No data in the source")} detail={section === "cash_flow" ? l("Лист движения денежных средств в бюджетной книге пока не заполнен - раздел появится сам, как только источник получит значения.", "The cash-flow sheet in the budget workbook has not been filled in yet - this section will populate itself once the source has values.") : l("Опубликованный бюджет не содержит строк этого раздела.", "The published budget contains no rows for this section.")} />}
  </Panel>;
}

const ACCOUNT_MAPPING_DATASET_LABELS: Record<string, [string, string]> = {
  accounting_balance_sheet: ["Баланс", "Balance sheet"],
  accounting_income_statement: ["ОПиУ", "Income statement"],
};

type AccountMappingEntry = { line_code: string; section?: string | null; current_label: string | null; first_seen: string | null; last_seen: string | null; label_history: Array<{ label: string; first_seen: string | null }>; label_drift: boolean; is_new: boolean };

export function AccountMappingPanel({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const mapping = (data.account_mapping ?? {}) as Record<string, AccountMappingEntry[]>;
  const flagged = Object.entries(mapping).flatMap(([datasetType, entries]) =>
    entries.filter((entry) => entry.label_drift || entry.is_new).map((entry) => ({ datasetType, ...entry }))
  );
  if (!flagged.length) return null;
  return <Panel title={l("Сверка кодов счетов", "Account-code mapping")} subtitle={l("Код строки — единственный устойчивый идентификатор между периодами; отдельного справочника счетов не загружается. Строки ниже требуют внимания перед построением сравнения периодов.", "The line code is the only durable identity across periods; no separate chart of accounts is imported. The rows below need a look before building a period comparison on top of them.")}>
    <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Набор", "Dataset")}</th><th>{l("Код", "Code")}</th><th>{l("Текущее наименование", "Current label")}</th><th>{l("История наименований", "Label history")}</th><th>{l("Впервые", "First seen")}</th><th>{l("Статус", "Status")}</th></tr></thead><tbody>{flagged.map((entry) => <tr key={`${entry.datasetType}-${entry.line_code}`}>
      <td>{ACCOUNT_MAPPING_DATASET_LABELS[entry.datasetType]?.[language === "en" ? 1 : 0] ?? entry.datasetType}</td>
      <td><strong>{entry.line_code}</strong></td>
      <td>{entry.current_label ?? "—"}</td>
      <td>{entry.label_history.map((item) => item.label).join(" → ")}</td>
      <td>{entry.first_seen ? formatDate(entry.first_seen, language) : "—"}</td>
      <td>{entry.is_new ? <span className="status-pill status-pill--info">{l("Новый код", "New code")}</span> : null} {entry.label_drift ? <span className="status-pill status-pill--warning">{l("Наименование изменилось", "Label changed")}</span> : null}</td>
    </tr>)}</tbody></table></div>
  </Panel>;
}

function AccountingPortfolioReconciliation({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const portfolioCode = String((data.summaries as Record<string, Record<string, unknown>>).accounting_portfolio_detail?.reconciliation_portfolio_code ?? "");
  const query = useQuery({ queryKey: ["operations-readiness"], queryFn: dashboardApi.operationsReadiness });
  if (!portfolioCode) return <p className="unavailable-note">{l("Портфель OSIP для сверки не выбран при загрузке этого файла; сверка не выполняется.", "No OSIP portfolio was selected when this file was uploaded; reconciliation does not run.")}</p>;
  if (query.isLoading) return null;
  const result = query.data?.reconciliations.find((item) => item.rule_code === "ACCOUNTING-PORTFOLIO" && item.scope_code === portfolioCode);
  if (!result) return <p className="unavailable-note">{l(`Сверка с портфелем OSIP «${portfolioCode}»: нет опубликованного снимка OSIP на сопоставимую дату.`, `Reconciliation with OSIP portfolio "${portfolioCode}": no published OSIP snapshot for a comparable date.`)}</p>;
  const accounting = result.actual_values.accounting;
  const osip = result.actual_values.osip;
  return <section className="reconciliation-workspace" aria-label={l("Сверка бухгалтерии с OSIP", "Accounting to OSIP reconciliation")}>
    <header>
      <div>
        <h3>{l(`Сверка бухгалтерии с OSIP · ${portfolioCode}`, `Accounting to OSIP reconciliation · ${portfolioCode}`)}</h3>
        <p>{l("Сопоставляется общий остаток балансовой стоимости на назначенную дату. Строки по категориям не рассчитываются: источник не содержит утверждённого ключа для такой сверки.", "Total carrying value is compared on the assigned date. Category-level tie-outs are not calculated because the source has no approved reconciliation key for them.")}</p>
      </div>
      <StatusPill status={result.status} />
    </header>
    <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Показатель", "Measure")}</th><th>{l("Бухгалтерия, KZT", "Accounting, KZT")}</th><th>{l("OSIP, KZT", "OSIP, KZT")}</th><th>{l("Разница, KZT", "Difference, KZT")}</th><th>{l("Допуск, KZT", "Tolerance, KZT")}</th><th>{l("Дата", "Date")}</th></tr></thead><tbody><tr>
      <td><strong>{l("Балансовая стоимость портфеля", "Portfolio carrying value")}</strong></td>
      <td>{accounting != null ? formatKzt(String(accounting), language) : "—"}</td>
      <td>{osip != null ? formatKzt(String(osip), language) : "—"}</td>
      <td>{result.difference != null ? formatKzt(String(result.difference), language) : "—"}</td>
      <td>{formatKzt(String(result.tolerance), language)}</td>
      <td>{result.business_date ? formatDate(result.business_date, language) : "—"}</td>
    </tr></tbody></table></div>
    {result.status === "date_mismatch" ? <p className="unavailable-note">{l("Даты источников различаются; разница показана, но не является сверкой на одну и ту же дату.", "The source dates differ; the difference is displayed but is not a same-date reconciliation.")}</p> : null}
  </section>;
}

function AccountingCashBalancesPanel({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const allRecords = ((data.records as Record<string, Row[]>).accounting_portfolio_detail ?? []);
  const rows = allRecords.filter((row) => row.record_type === "cash_balance");
  if (!rows.length) return null;
  const total = rows.reduce((sum, row) => sum + Number(row.amount_kzt ?? 0), 0);
  return <Panel title={l("Денежные средства портфеля", "Portfolio cash balances")} subtitle={l("Остатки денежных средств по банкам и валютам из того же листа ОСИП_ПОРТФЕЛЬ, что и позиции выше; их сумма входит в показатель «Балансовая стоимость портфеля» ниже, но не в таблицу позиций.", "Cash balances by bank and currency from the same ОСИП_ПОРТФЕЛЬ sheet as the positions above; their sum is included in the portfolio carrying-value figure below but not in the positions table.")} action={<SourceRowLegend language={language} />}>
    <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Валюта", "Currency")}</th><th>{l("Банк/депозитарий", "Bank / depository")}</th><th>{l("Сумма, KZT", "Amount, KZT")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)}><td>{displayValue("currency", row.currency, language)}</td><td>{displayValue("custodian", row.custodian, language)}</td><td>{displayValue("amount_kzt", row.amount_kzt, language)}</td><SourceCell row={row} language={language} /></tr>)}<tr><td colSpan={2}><strong>{l("Итого", "Total")}</strong></td><td><strong>{formatKzt(String(total), language)}</strong></td><td /></tr></tbody></table></div>
  </Panel>;
}

export function AccountingPortfolioPanel({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const [page, setPage] = useState(0);
  const pagination = useScrollAnchor<HTMLDivElement>();
  const allRecords = ((data.records as Record<string, Row[]>).accounting_portfolio_detail ?? []);
  const records = allRecords.filter((row) => row.record_type !== "cash_balance");
  const pageSize = STANDARD_TABLE_PAGE_SIZE;
  const pageCount = Math.max(1, Math.ceil(records.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const visibleRows = records.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  return <>
  <Panel title={l("Детализация портфеля", "Portfolio detail")} subtitle={l(`Показано ${visibleRows.length} из ${records.length} позиций; балансовая и рыночная стоимость в тенге напрямую из книги учёта портфеля - отдельного источника от бухгалтерского баланса, поэтому суммы не тождественны построчно. Показатель «Балансовая стоимость портфеля» ниже включает и эти позиции, и денежные средства (см. «Денежные средства портфеля»).`, `${visibleRows.length} of ${records.length} positions shown; carrying and market value in KZT come straight from the portfolio ledger - a separate source from the balance sheet, so the totals are not line-for-line identical. The "Portfolio carrying value" figure below includes both these positions and cash (see "Portfolio cash balances").`)} action={records.length ? <div className="table-tools"><TableSearch label={l("Поиск детализации портфеля", "Search portfolio detail")} placeholder={l("Инструмент, ISIN, класс", "Instrument, ISIN, class")} /><SourceRowLegend language={language} /></div> : undefined}>
    {records.length ? <AccountingPortfolioReconciliation data={data} language={language} /> : null}
    {records.length ? <><div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Категория", "Category")}</th><th>{l("Эмитент", "Issuer")}</th><th>ISIN</th><th>{l("Валюта", "Currency")}</th><th>{l("Количество", "Quantity")}</th><th>{l("Цена покупки", "Purchase price")}</th><th>{l("Балансовая стоимость, KZT", "Carrying value, KZT")}</th><th>{l("Рыночная стоимость, KZT", "Market value, KZT")}</th><th>{l("Накопленный доход, KZT", "Accrued income, KZT")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{visibleRows.map((row, index) => <tr key={String(row.id ?? index)}><td>{displayValue("category", row.category, language)}</td><td>{displayValue("issuer", row.issuer, language)}</td><td>{displayValue("isin", row.isin, language)}</td><td>{displayValue("currency", row.currency, language)}</td><td>{displayValue("quantity", row.quantity, language)}</td><td>{displayValue("purchase_price", row.purchase_price, language)}</td><td>{displayValue("carrying_value_kzt", row.carrying_value_kzt, language)}</td><td>{displayValue("market_value_kzt", row.market_value_kzt, language)}</td><td>{displayValue("accrued_income_kzt", row.accrued_income_kzt, language)}</td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div><div className="table-pagination" ref={pagination.ref}><span>{l(`Страница ${currentPage + 1} из ${pageCount} · ${pageSize} строк на странице`, `Page ${currentPage + 1} of ${pageCount} · ${pageSize} rows per page`)}</span><label className="table-pagination__jump"><span>{l("Перейти", "Go to")}</span><select aria-label={l("Выбрать страницу", "Choose page")} value={currentPage} onChange={(event) => { pagination.anchor(); setPage(Number(event.target.value)); }}>{Array.from({ length: pageCount }, (_, index) => <option key={index} value={index}>{index + 1}</option>)}</select></label><div><button className="icon-button" type="button" aria-label={l("Предыдущая страница", "Previous page")} disabled={currentPage === 0} onClick={() => { pagination.anchor(); setPage((value) => Math.max(0, value - 1)); }}><ChevronLeft aria-hidden="true" /></button><button className="icon-button" type="button" aria-label={l("Следующая страница", "Next page")} disabled={currentPage >= pageCount - 1} onClick={() => { pagination.anchor(); setPage((value) => Math.min(pageCount - 1, value + 1)); }}><ChevronRight aria-hidden="true" /></button></div></div></> : <EmptyState title={l("Позиции не найдены", "No positions found")} detail={l("Опубликованный источник не содержит строк детализации портфеля.", "The published source has no portfolio-detail rows.")} />}
  </Panel>
  <AccountingCashBalancesPanel data={data} language={language} />
  </>;
}

export function AccountingIncomeStatementPanel({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const [page, setPage] = useState(0);
  const pagination = useScrollAnchor<HTMLDivElement>();
  const records = ((data.records as Record<string, Row[]>).accounting_income_statement ?? []);
  const pageSize = STANDARD_TABLE_PAGE_SIZE;
  const pageCount = Math.max(1, Math.ceil(records.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const visibleRows = records.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  return <Panel title={l("Отчёт о прибылях и убытках", "Income statement")} subtitle={l(`Показано ${visibleRows.length} из ${records.length} строк; каждая строка сохраняет ссылку на исходную рабочую книгу.`, `${visibleRows.length} of ${records.length} rows shown; every row retains a source-workbook reference.`)} action={records.length ? <div className="table-tools"><TableSearch label={l("Поиск строк отчёта о прибылях и убытках", "Search income-statement rows")} placeholder={l("Код, статья, раздел", "Code, line, section")} /><SourceRowLegend language={language} /></div> : undefined}>
    {records.length ? <><div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Код строки", "Line code")}</th><th>{l("Наименование статьи", "Line label")}</th><th>{l("За отчетный квартал", "Quarter")}</th><th>{l("С начала года", "YTD")}</th><th>{l("Аналог. квартал пред. года", "Prior-year quarter")}</th><th>{l("С начала пред. года", "Prior-year YTD")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{visibleRows.map((row, index) => <tr key={String(row.id ?? index)}><td>{displayValue("line_code", row.line_code, language)}</td><td>{displayValue("line_label", row.line_label, language)}</td><td>{displayValue("quarter_kzt", row.quarter_kzt, language)}</td><td>{displayValue("ytd_kzt", row.ytd_kzt, language)}</td><td>{displayValue("prior_quarter_kzt", row.prior_quarter_kzt, language)}</td><td>{displayValue("prior_ytd_kzt", row.prior_ytd_kzt, language)}</td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div><div className="table-pagination" ref={pagination.ref}><span>{l(`Страница ${currentPage + 1} из ${pageCount} · ${pageSize} строк на странице`, `Page ${currentPage + 1} of ${pageCount} · ${pageSize} rows per page`)}</span><label className="table-pagination__jump"><span>{l("Перейти", "Go to")}</span><select aria-label={l("Выбрать страницу", "Choose page")} value={currentPage} onChange={(event) => { pagination.anchor(); setPage(Number(event.target.value)); }}>{Array.from({ length: pageCount }, (_, index) => <option key={index} value={index}>{index + 1}</option>)}</select></label><div><button className="icon-button" type="button" aria-label={l("Предыдущая страница", "Previous page")} disabled={currentPage === 0} onClick={() => { pagination.anchor(); setPage((value) => Math.max(0, value - 1)); }}><ChevronLeft aria-hidden="true" /></button><button className="icon-button" type="button" aria-label={l("Следующая страница", "Next page")} disabled={currentPage >= pageCount - 1} onClick={() => { pagination.anchor(); setPage((value) => Math.min(pageCount - 1, value + 1)); }}><ChevronRight aria-hidden="true" /></button></div></div></> : <EmptyState title={l("Отчёт не найден", "No income statement found")} detail={l("В опубликованном источнике нет строк отчёта о прибылях и убытках.", "The published source has no income-statement rows.")} />}
  </Panel>;
}

export function AccountingVersionPickerBar({ data, selections, onSelect, language }: { data: ModuleReadResponse; selections: Record<string, string | null>; onSelect: (datasetType: string, datasetId: string | null) => void; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const sources = Object.keys(ACCOUNTING_DATASET_TYPE_LABELS)
    .map((datasetType) => data.sources.find((source) => source.dataset_type === datasetType))
    .filter((source): source is ModuleReadResponse["sources"][number] => Boolean(source));
  if (!sources.length) return null;
  return <section className="filterbar filterbar--domain-version filterbar--accounting-version" aria-label={l("Версии бухгалтерских рабочих книг", "Accounting workbook versions")}>
    {sources.map((source) => {
      const label = ACCOUNTING_DATASET_TYPE_LABELS[source.dataset_type];
      return <label className="filterbar__snapshot" key={source.dataset_type}>
        <span>{label ? (language === "en" ? label[1] : label[0]) : source.dataset_type} · {l("Версия рабочей книги", "Workbook version")}</span>
        <DatasetVersionPicker source={source} selectedDatasetId={selections[source.dataset_type] ?? null} onSelect={(datasetId) => onSelect(source.dataset_type, datasetId)} language={language} />
      </label>;
    })}
    <small>{l("Каждый источник загружается независимо; версии выбираются отдельно.", "Each source is uploaded independently; choose each version separately.")}</small>
  </section>;
}
