import type { ModuleReadResponse } from "../../api/types";
import { Panel } from "../../components/ui/Panel";
import { StatusPill } from "../../components/ui/StatusPill";
import { SourceRowLegend } from "../../components/ui/SourceRowLegend";
import { formatKzt } from "../../lib/format";
import { displayValue, money, DatasetVersionPicker, SourceCell, VersionPicker, type Row } from "./shared";

// TABYS is fed by two genuinely independent physical workbooks: valuation/
// holdings/cash/NAV-history/prices/inactive-evidence all come from one
// "Портфель" file (pinned together via source_upload_id, like every other
// single-workbook module), while unit-value history comes from its own
// separate "Стоимость пая" file with its own, unrelated version history.
// Pinning only the valuation file's version previously left the unit-value
// chart silently empty with no indication why - this gives it its own
// picker instead, matching how Risk/Accounting already handle their own
// multiple independent source files.
export function AssetManagementVersionPickerBar({
  data, selectedSourceUploadId, onSelectPackage, selectedUnitSeriesId, onSelectUnitSeries, language,
}: {
  data: ModuleReadResponse;
  selectedSourceUploadId: string | null;
  onSelectPackage: (sourceUploadId: string | null) => void;
  selectedUnitSeriesId: string | null;
  onSelectUnitSeries: (datasetId: string | null) => void;
  language: "ru" | "en";
}) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const valuationSource = data.sources.find((source) => source.dataset_type === "fund_valuation");
  const unitSeriesSource = data.sources.find((source) => source.dataset_type === "fund_unit_series");
  if (!valuationSource && !unitSeriesSource) return null;
  return <section className="filterbar filterbar--domain-version filterbar--accounting-version" aria-label={l("Версии рабочих книг TABYS", "TABYS workbook versions")}>
    {valuationSource ? <label className="filterbar__snapshot">
      <span>{l("Портфель и оценка", "Portfolio and valuation")} · {l("Версия рабочей книги", "Workbook version")}</span>
      <VersionPicker source={valuationSource} selectedSourceUploadId={selectedSourceUploadId} onSelect={onSelectPackage} language={language} />
    </label> : null}
    {unitSeriesSource ? <label className="filterbar__snapshot">
      <span>{l("Стоимость пая", "Unit value")} · {l("Версия рабочей книги", "Workbook version")}</span>
      <DatasetVersionPicker source={unitSeriesSource} selectedDatasetId={selectedUnitSeriesId} onSelect={onSelectUnitSeries} language={language} />
    </label> : null}
    <small>{l("Каждый источник загружается независимо; версии выбираются отдельно.", "Each source is uploaded independently; choose each version separately.")}</small>
  </section>;
}

export function FundControlsPanel({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const summaries = data.summaries as Record<string, Record<string, unknown>>;
  const valuation = summaries.fund_valuation ?? {};
  const prices = summaries.fund_prices ?? {};
  const records = data.records as Record<string, Row[]>;
  const missingPriceRows = (records.fund_prices ?? []).filter((row) => row.price == null || row.price === "").slice(0, 25);
  const n = (value: unknown) => value == null || value === "" ? null : Number(value);
  const securities = n(valuation.securities_value_kzt); const cash = n(valuation.cash_kzt); const liabilities = n(valuation.liabilities_kzt); const nav = n(valuation.nav_kzt);
  const calculated = securities == null || cash == null || liabilities == null ? null : securities + cash - liabilities;
  const difference = calculated == null || nav == null ? null : calculated - nav;
  const priceCount = n(prices.price_count) ?? 0; const missing = n(prices.missing_price_count) ?? 0;
  return <Panel title={l("Контроли фонда и покрытие цен", "Fund controls and price coverage")} subtitle={l("Сверка TABYS с источником оценки.", "TABYS valuation tie-outs.")} action={missingPriceRows.length ? <SourceRowLegend language={language} /> : undefined}>
    <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Контроль", "Control")}</th><th>{l("Значение", "Value")}</th><th>{l("Статус", "Status")}</th><th>{l("Основа", "Basis")}</th></tr></thead><tbody>
      <tr><td>{l("Ценные бумаги + деньги − обязательства", "Securities + cash − liabilities")}</td><td>{calculated == null ? "—" : formatKzt(String(calculated), language)}</td><td><StatusPill status={difference != null && Math.abs(difference) <= 1 ? "pass" : "warning"} /></td><td>{l("Расчёт по источнику", "Source-derived")}</td></tr>
      <tr><td>{l("СЧА из рабочей книги", "Source-reported NAV")}</td><td>{money(valuation.nav_kzt, language)}</td><td><StatusPill status="source" /></td><td>{l("Источник", "Source")}</td></tr>
      <tr><td>{l("Разница сверки", "Reconciliation difference")}</td><td>{difference == null ? "—" : formatKzt(String(difference), language)}</td><td><StatusPill status={difference != null && Math.abs(difference) <= 1 ? "pass" : "warning"} /></td><td>{l("Допуск 1 KZT", "1 KZT tolerance")}</td></tr>
      <tr><td>{l("Покрытие цен", "Price coverage")}</td><td>{priceCount ? `${Math.max(0, priceCount - missing)} / ${priceCount}` : "—"}</td><td><StatusPill status={missing === 0 ? "pass" : "warning"} /></td><td>{String(prices.latest_price_date ?? "—")}</td></tr>
    </tbody></table></div>
    {/* "Evidence-only partitions" (fund_inactive_evidence: sheet/rows/formula-error/
        external-link counts for non-position sheets like deposits/REPO/other-property)
        hidden on web by request - the underlying dataset stays in the Excel export. */}
    {missingPriceRows.length ? <div className="table-scroll" tabIndex={0}><h3>{l("Цены без значения", "Missing prices")}</h3><table><thead><tr><th>{l("Тикер", "Ticker")}</th><th>{l("Наименование", "Name")}</th><th>{l("Валюта", "Currency")}</th><th>{l("Дата цены", "Price date")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{missingPriceRows.map((row, index) => <tr key={String(row.id ?? index)}><td>{String(row.ticker ?? "—")}</td><td>{String(row.name ?? "—")}</td><td>{String(row.currency ?? "—")}</td><td>{displayValue("date", row.price_date, language)}</td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div> : null}
  </Panel>;
}
