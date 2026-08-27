import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { dashboardApi } from "../../api/client";
import type { ModuleReadResponse } from "../../api/types";
import { DatasetVersionComparison } from "../../components/ui/DatasetVersionComparison";
import { Panel } from "../../components/ui/Panel";
import { SourceRowLegend } from "../../components/ui/SourceRowLegend";
import { StatusPill } from "../../components/ui/StatusPill";
import { TableSearch } from "../../components/ui/TableSearch";
import { useProvenance } from "../../components/ui/ProvenanceContext";
import { formatDate, formatPercent, humanize } from "../../lib/format";
import { useScrollAnchor } from "../../hooks/useScrollAnchor";
import { DatasetVersionPicker, displayValue, SourceCell, STANDARD_TABLE_PAGE_SIZE, type Row } from "./shared";

// The near-breach classification (utilization ratio, near_breach flag, and
// the threshold that produced it) is computed once, at parse time, by
// _risk_utilization/_risk_near_breach in ingestion/multi_source.py - never
// recomputed here, so the UI always shows exactly what was classified (and
// stays correct if the documented threshold policy ever changes) instead of
// risking a second, silently-diverging copy of the same rule.
const RISK_NEAR_BREACH_THRESHOLD_FALLBACK = 0.9;
export function riskUtilization(row: Row): number | null {
  return row.utilization == null || row.utilization === "" ? null : Number(row.utilization);
}
export function isRiskNearBreach(row: Row): boolean {
  return Boolean(row.near_breach);
}
export function riskNearBreachThreshold(rows: Row[]): number {
  const withThreshold = rows.find((row) => row.near_breach_threshold != null);
  return withThreshold ? Number(withThreshold.near_breach_threshold) : RISK_NEAR_BREACH_THRESHOLD_FALLBACK;
}

// The "Detail" sheet already carries a country x instrument-category
// breakdown as flat rows (one per pair); this renders the same records as an
// actual cross-tab so a concentration across both dimensions reads at a
// glance instead of requiring a scan through 60+ flat rows. Each country's
// amounts are in that country's own currency (a single header sets the
// currency per country block in the source), so a grand total or a
// column-of-categories total across countries would silently mix
// currencies - only a per-row (per-country) total is shown, and it is
// explicitly labelled with that row's currency.
function RiskCountryInstrumentPivot({ rows, language }: { rows: Row[]; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const { openSourcePreview } = useProvenance();
  if (!rows.length) return null;
  // A country block can exist in the source even when every category cell is
  // blank or explicitly zero. Do not render those empty blocks. Values that
  // are present but non-numeric are retained as source evidence rather than
  // guessed away.
  const populatedRows = rows.filter((row) => {
    const value = row.amount_native;
    if (value == null) return false;
    if (typeof value === "number") return value !== 0;
    const text = String(value).trim();
    if (!text || text === "-" || text === "—") return false;
    const numeric = Number(text.replace(/\s/g, "").replace(",", "."));
    return Number.isFinite(numeric) ? numeric !== 0 : true;
  });
  if (!populatedRows.length) return null;
  const categories = [...new Set(populatedRows.map((row) => String(row.instrument_category ?? "")))].sort();
  const countryCurrency = new Map<string, string>();
  const matrix = new Map<string, Map<string, Row>>();
  for (const row of populatedRows) {
    const country = String(row.country ?? "");
    const category = String(row.instrument_category ?? "");
    if (!countryCurrency.has(country)) countryCurrency.set(country, String(row.currency ?? ""));
    if (!matrix.has(country)) matrix.set(country, new Map());
    matrix.get(country)!.set(category, row);
  }
  const rowTotal = (country: string) => categories.reduce((sum, category) => sum + (Number(matrix.get(country)?.get(category)?.amount_native) || 0), 0);
  const countries = [...countryCurrency.keys()].sort((a, b) => rowTotal(b) - rowTotal(a));
  const openCellSource = (cell: Row | undefined) => {
    const source = cell?.source;
    if (!source || typeof source !== "object" || Array.isArray(source)) return;
    const value = source as Record<string, unknown>;
    const sourceCell = value.source_cell;
    const sheetName = value.sheet_name;
    const rowId = cell?.id;
    if (typeof sourceCell !== "string" || typeof sheetName !== "string" || typeof rowId !== "string") return;
    openSourcePreview({
      source_kind: "row",
      source_row_id: rowId,
      source_cell: sourceCell,
      sheet_name: sheetName,
      workbook_name: String(value.filename ?? value.workbook_name ?? ""),
      parser_version: "",
    });
  };
  return <Panel title={l("Свод по странам и категориям инструментов", "Country x instrument-category summary")} subtitle={l("Тот же лист «Detail» в виде перекрёстной таблицы. Суммы приведены в валюте каждой страны — итог по строке корректен, но столбец с итогом по категориям через все страны не рассчитывается, так как валюты разные.", "The same “Detail” sheet as a cross-tab. Amounts are in each country's own currency - a row total is valid, but no across-country column total is computed since currencies differ.")} action={<TableSearch label={l("Поиск свода по странам", "Search country summary")} placeholder={l("Страна, валюта, категория", "Country, currency, category")} />}>
    <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Страна", "Country")}</th>{categories.map((category) => <th key={category}>{category}</th>)}<th>{l("Итого (валюта страны)", "Total (country currency)")}</th></tr></thead><tbody>{countries.map((country) => {
      const currency = countryCurrency.get(country);
      return <tr key={country}>
        <td><strong>{displayValue("country", country, language)}</strong> <small>{currency}</small></td>
        {categories.map((category) => {
          const cell = matrix.get(country)?.get(category);
          return <td
            key={category}
            className={cell ? "pivot-cell pivot-cell--clickable" : "pivot-cell"}
            title={cell ? l("Показать исходную ячейку", "Show source cell") : undefined}
            onClick={() => openCellSource(cell)}
          >{cell ? displayValue("amount_native", cell.amount_native, language) : "—"}</td>;
        })}
        <td><strong>{displayValue("amount_native", String(rowTotal(country)), language)}</strong></td>
      </tr>;
    })}</tbody></table></div>
  </Panel>;
}

// The fill width matches the displayed percentage 1:1 (capped at 100% of
// the limit) so the bar and the number next to it never disagree. A breach
// (over 100% of the limit) still reads as "how bad" via color, since the
// exact percentage is already in the value text above the bar.
function RiskUtilizationCell({ utilization, breach, language }: { utilization: number; breach: boolean; language: "ru" | "en" }) {
  const fillPercent = Math.min(100, utilization * 100);
  return (
    <div className="risk-utilization-cell">
      <span className="risk-utilization-cell__value">{formatPercent(utilization * 100, 0, language)}</span>
      <span className="risk-utilization-cell__track" aria-hidden="true">
        <span className={`risk-utilization-cell__fill${breach ? " risk-utilization-cell__fill--breach" : ""}`} style={{ width: `${fillPercent}%` }} />
      </span>
    </div>
  );
}

export function RiskControlsPanel({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const records = data.records as Record<string, Row[]>;
  const summaries = data.summaries as Record<string, Record<string, unknown>>;
  const duration = [...(records.risk_limits_sobstv ?? []), ...(records.risk_limits_tabys ?? [])].filter((row) => row.dimension === "duration");
  const exposure = (records.risk_limits_sobstv ?? []).filter((row) => row.dimension === "exposure_detail");
  const countryDetail = (records.risk_limits_sobstv ?? []).filter((row) => row.dimension === "country_instrument_detail");
  const controlRecords = [...(records.risk_limits_sobstv ?? []), ...(records.risk_limits_tabys ?? [])]
    .filter((row) => row.dimension !== "exposure_detail" && row.dimension !== "country_instrument_detail");
  const watchlist = controlRecords
    .filter((row) => row.signal === "breach" || isRiskNearBreach(row))
    .sort((a, b) => (riskUtilization(b) ?? 0) - (riskUtilization(a) ?? 0));
  const watchlistPage = useStandardTablePagination(watchlist, 10);
  const durationPage = useStandardTablePagination(duration, 10);
  const exposurePage = useStandardTablePagination(exposure, 10);
  const countryDetailPage = useStandardTablePagination(countryDetail, 10);
  const portfolioRows = [["SOBSTV", summaries.risk_limits_sobstv ?? {}], ["TABYS", summaries.risk_limits_tabys ?? {}]] as const;
  const nearBreachThresholdPercent = riskNearBreachThreshold(controlRecords) * 100;
  return <>
    <Panel title={l("Список наблюдения: превышения и риск превышения", "Watchlist: breaches and near-breaches")} subtitle={l(`Превышенные лимиты и строки с использованием лимита ${nearBreachThresholdPercent}% и выше, отсортированные по использованию.`, `Breached limits and lines at ${nearBreachThresholdPercent}%+ utilization, sorted by utilization.`)} action={watchlist.length ? <div className="table-tools"><TableSearch label={l("Поиск списка наблюдения", "Search risk watchlist")} placeholder={l("Портфель, измерение, название", "Portfolio, dimension, name")} /><SourceRowLegend language={language} /></div> : undefined}>
      {watchlist.length
        ? <><div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Портфель", "Portfolio")}</th><th>{l("Измерение", "Dimension")}</th><th>{l("Наименование", "Label")}</th><th>{l("Использование", "Utilization")}</th><th>{l("Лимит", "Limit")}</th><th>{l("Факт", "Actual")}</th><th>{l("Запас", "Headroom")}</th><th>{l("Сигнал", "Signal")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{watchlistPage.visibleRows.map((row, index) => {
          const utilization = riskUtilization(row);
          const limitKey = row.limit_pct != null ? "limit_pct" : row.limit_kzt != null ? "limit_kzt" : "limit_usd";
          const actualKey = row.actual_pct != null ? "actual_pct" : row.actual_kzt != null ? "actual_kzt" : "actual_usd";
          return <tr key={String(row.id ?? index)}><td><strong>{displayValue("portfolio_code", row.portfolio_code, language)}</strong></td><td>{humanize(String(row.dimension ?? ""), language)}</td><td>{displayValue("label", row.label, language)}</td><td>{utilization != null ? <RiskUtilizationCell utilization={utilization} breach={row.signal === "breach"} language={language} /> : "—"}</td><td>{displayValue(limitKey, row[limitKey], language)}</td><td>{displayValue(actualKey, row[actualKey], language)}</td><td>{displayValue("free_limit_kzt", row.free_limit_kzt, language)}</td><td><StatusPill status={row.signal === "breach" ? "breach" : "near_breach"} /></td><SourceCell row={row} language={language} /></tr>;
        })}</tbody></table></div><StandardTablePagination {...watchlistPage} language={language} /></>
        : <div className="unavailable-note">{l("Превышений и близких к превышению строк не обнаружено.", "No breaches or near-breach lines detected.")}</div>}
    </Panel>
    <Panel title={l("Покрытие риск-контролей", "Risk-control coverage")} subtitle={l("Сводка разделяет контрольные строки, информационные детали и неопределённые статусы. Строки без собственного порога не считаются превышением.", "Coverage separates control lines, informational detail, and unresolved statuses. Rows without their own threshold are not treated as breaches.")}>
      <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Портфель", "Portfolio")}</th><th>{l("Дата", "Date")}</th><th>{l("Контроли", "Controls")}</th><th>{l("Детали", "Details")}</th><th>{l("Превышения", "Breaches")}</th><th>{l("Не определено", "Unknown")}</th><th>{l("Без лимита", "No limit")}</th><th>{l("Измерения", "Dimensions")}</th><th>{l("Версии", "Versions")}</th></tr></thead><tbody>{portfolioRows.map(([portfolio, summary]) => { const source = data.sources.find((item) => item.scope_code === portfolio); return <tr key={portfolio}><td><strong>{portfolio}</strong></td><td>{source?.business_date ? formatDate(source.business_date, language) : "—"}</td><td>{String(summary.limit_count ?? 0)}</td><td>{String(summary.detail_count ?? 0)}</td><td><StatusPill status={Number(summary.breach_count ?? 0) ? "breach" : "ok"} /> {String(summary.breach_count ?? 0)}</td><td>{Number(summary.unknown_count ?? 0) ? <StatusPill status="unknown" /> : null} {String(summary.unknown_count ?? 0)}</td><td>{String(summary.not_applicable_count ?? 0)}</td><td>{Object.entries((summary.dimension_counts ?? {}) as Record<string, unknown>).map(([key, value]) => `${key}: ${value}`).join(" · ") || "—"}</td><td><RiskVersionComparison portfolio={portfolio} language={language} /></td></tr>; })}</tbody></table></div>
    </Panel>
    {duration.length ? <Panel title={l("Контроли дюрации", "Duration controls")} subtitle={l("Отдельный лист «Лимит по дюрации»: модифицированная дюрация сопоставлена с утверждённым максимумом по каждой позиции.", "The separate duration sheet: modified duration is compared with the approved maximum for each position.")} action={<div className="table-tools"><TableSearch label={l("Поиск контролей дюрации", "Search duration controls")} placeholder={l("Эмитент, ISIN, страна", "Issuer, ISIN, country")} /><SourceRowLegend language={language} /></div>}>
      <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Эмитент", "Issuer")}</th><th>ISIN</th><th>{l("Страна", "Country")}</th><th>{l("Валюта", "Currency")}</th><th>{l("Лимит", "Limit")}</th><th>{l("Модифицированная", "Modified")}</th><th>{l("Запас", "Headroom")}</th><th>{l("Сигнал", "Signal")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{durationPage.visibleRows.map((row, index) => <tr key={String(row.id ?? index)}><td>{displayValue("issuer", row.issuer ?? row.label, language)}</td><td>{displayValue("isin", row.isin, language)}</td><td>{displayValue("country", row.country, language)}</td><td>{displayValue("currency", row.currency, language)}</td><td>{displayValue("duration_limit", row.duration_limit, language)}</td><td>{displayValue("modified_duration", row.modified_duration, language)}</td><td>{displayValue("duration_headroom", row.duration_headroom, language)}</td><td><StatusPill status={String(row.signal ?? "unknown")} /></td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div><StandardTablePagination {...durationPage} language={language} />
    </Panel> : null}
    {exposure.length ? <Panel title={l("Расшифровка валютной экспозиции", "Currency exposure detail")} subtitle={l("Лист «Расшифровка» сохранён как детализация по инструменту и валюте; суммы не смешиваются с лимитными строками.", "The “Расшифровка” sheet is retained as instrument/currency detail; amounts are not mixed into limit-line controls.")} action={<div className="table-tools"><TableSearch label={l("Поиск валютной экспозиции", "Search currency exposure")} placeholder={l("Валюта, инструмент, группа", "Currency, instrument, group")} /><SourceRowLegend language={language} /></div>}>
      <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Валюта", "Currency")}</th><th>{l("Инструмент / счёт", "Instrument / account")}</th><th>{l("Группа лимита", "Limit group")}</th><th>{l("Сумма в валюте", "Native amount")}</th><th>{l("Курс", "FX rate")}</th><th>{l("Сумма, KZT", "KZT amount")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{exposurePage.visibleRows.map((row, index) => <tr key={String(row.id ?? index)}><td>{displayValue("currency", row.currency, language)}</td><td>{displayValue("label", row.label, language)}</td><td>{displayValue("instrument_group", row.instrument_group, language)}</td><td>{displayValue("amount_native", row.amount_native, language)}</td><td>{displayValue("fx_rate", row.fx_rate, language)}</td><td>{displayValue("amount_kzt", row.amount_kzt, language)}</td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div>
      <StandardTablePagination {...exposurePage} language={language} />
    </Panel> : null}
    <RiskCountryInstrumentPivot rows={countryDetail} language={language} />
    {countryDetail.length ? <Panel title={l("Детализация по странам и инструментам", "Country and instrument detail")} subtitle={l("Лист «Detail»: подытоги по стране и категории инструмента (не лимитная строка). Это сводка, а не построчная детализация: отдельные позиции внутри каждого подытога в это представление не включены.", "The “Detail” sheet: subtotals by country and instrument category (informational, not a limit control). This is summary-level evidence, not a full position-level breakdown - individual positions within each subtotal are not included here.")} action={<div className="table-tools"><TableSearch label={l("Поиск детализации по странам", "Search country detail")} placeholder={l("Страна, категория, валюта", "Country, category, currency")} /><SourceRowLegend language={language} /></div>}>
      <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Страна", "Country")}</th><th>{l("Валюта", "Currency")}</th><th>{l("Категория инструмента", "Instrument category")}</th><th>{l("Сумма в валюте", "Native amount")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{countryDetailPage.visibleRows.map((row, index) => <tr key={String(row.id ?? index)}><td>{displayValue("country", row.country, language)}</td><td>{displayValue("currency", row.currency, language)}</td><td>{displayValue("instrument_category", row.instrument_category, language)}</td><td>{displayValue("amount_native", row.amount_native, language)}</td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div>
      <StandardTablePagination {...countryDetailPage} language={language} />
    </Panel> : null}
  </>;
}

// Reuses the generic dataset-versions compare endpoint already used on the
// Imports registry (DatasetVersionComparison) - risk gets version
// comparison for free rather than a bespoke risk diff view.
function RiskVersionComparison({ portfolio, language }: { portfolio: string; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const datasetType = portfolio === "TABYS" ? "risk_limits_tabys" : "risk_limits_sobstv";
  const versions = useQuery({ queryKey: ["dataset-versions", datasetType, portfolio], queryFn: () => dashboardApi.datasetVersions(datasetType, portfolio) });
  const items = [...(versions.data?.items ?? [])].sort((a, b) => b.version - a.version);
  if (items.length < 2) return <span className="unavailable-note unavailable-note--pill">{l("Нет прошлой версии", "No prior version")}</span>;
  return <DatasetVersionComparison dataset={items[0]} baseline={items[1]} />;
}

function useStandardTablePagination<T>(rows: T[], pageSize = STANDARD_TABLE_PAGE_SIZE) {
  const [page, setPage] = useState(0);
  const pagination = useScrollAnchor<HTMLDivElement>();
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const visibleRows = rows.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  useEffect(() => { setPage(0); }, [rows.length]);
  const onPageChange = (nextPage: number) => {
    pagination.anchor();
    setPage(Math.max(0, Math.min(pageCount - 1, nextPage)));
  };
  return { visibleRows, currentPage, pageCount, pagination, onPageChange, pageSize };
}

function StandardTablePagination({ currentPage, pageCount, pagination, onPageChange, pageSize, language }: ReturnType<typeof useStandardTablePagination<unknown>> & { language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  if (pageCount <= 1) return null;
  return <div className="table-pagination" ref={pagination.ref}>
    <span>{l(`Страница ${currentPage + 1} из ${pageCount} · ${pageSize} строк на странице`, `Page ${currentPage + 1} of ${pageCount} · ${pageSize} rows per page`)}</span>
    <label className="table-pagination__jump"><span>{l("Перейти", "Go to")}</span><select aria-label={l("Выбрать страницу", "Choose page")} value={currentPage} onChange={(event) => onPageChange(Number(event.target.value))}>{Array.from({ length: pageCount }, (_, index) => <option key={index} value={index}>{index + 1}</option>)}</select></label>
    <div><button className="icon-button" type="button" aria-label={l("Предыдущая страница", "Previous page")} disabled={currentPage === 0} onClick={() => onPageChange(currentPage - 1)}><ChevronLeft aria-hidden="true" /></button><button className="icon-button" type="button" aria-label={l("Следующая страница", "Next page")} disabled={currentPage >= pageCount - 1} onClick={() => onPageChange(currentPage + 1)}><ChevronRight aria-hidden="true" /></button></div>
  </div>;
}

export function RiskVersionPickerBar({ data, selections, onSelect, language }: { data: ModuleReadResponse; selections: Record<string, string | null>; onSelect: (scopeCode: string, datasetId: string | null) => void; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const sources = ["SOBSTV", "TABYS"].map((scope) => data.sources.find((source) => source.scope_code === scope)).filter((source): source is ModuleReadResponse["sources"][number] => Boolean(source));
  return <section className="filterbar filterbar--domain-version" aria-label={l("Версии рабочих книг риска", "Risk workbook versions")}>
    {sources.map((source) => <label className="filterbar__snapshot" key={source.scope_code}>
      <span>{source.scope_code} · {l("Версия рабочей книги", "Workbook version")}</span>
      <DatasetVersionPicker source={source} selectedDatasetId={selections[source.scope_code] ?? null} onSelect={(datasetId) => onSelect(source.scope_code, datasetId)} language={language} />
    </label>)}
    <small>{l("SOBSTV и TABYS — независимые источники; версии выбираются отдельно.", "SOBSTV and TABYS are independent sources; choose each version separately.")}</small>
  </section>;
}
