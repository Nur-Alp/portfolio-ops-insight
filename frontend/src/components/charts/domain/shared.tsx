import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { formatDate, formatKzt, formatNumber } from "../../../lib/format";
import { BasisBadge } from "../../ui/BasisBadge";
import { useProvenance } from "../../ui/ProvenanceContext";
import type { components } from "../../../api/schema";

// Shared types, constants, low-level chart building blocks, and generic
// helper functions used by more than one domain's chart cluster. Anything
// that only ever appears inside a single domain's `if (kind === ...)` block
// in the original DomainCharts.tsx lives in that domain's own file instead.

export type Language = "ru" | "en";
export type Row = Record<string, unknown>;
export type ChartDatum = Record<string, string | number>;
export type ProvenanceRef = NonNullable<components["schemas"]["MetricProvenance"]["source_refs"]>[number];
export type MetricProvenance = components["schemas"]["MetricProvenance"];

export const COLORS = ["#9226a8", "#3d6fd8", "#27a36a", "#e9a23b", "#cf4253", "#7b67c8", "#4ca7a5"];
export const GRID = "#e3e7ef";
export const MUTED = "#667085";
export const axisTick = { fill: MUTED, fontSize: 11 };

export function ChartGrid({ children, single = false }: React.PropsWithChildren<{ single?: boolean }>) {
  return <section className={`insight-chart-grid ${single ? "insight-chart-grid--single" : ""}`}>{children}</section>;
}

export function ChartCard({ title, subtitle, basis, sourceRefs = [], provenance, compact = false, wide = false, footer, children }: React.PropsWithChildren<{ title: string; subtitle: string; basis: "source" | "derived"; sourceRefs?: ProvenanceRef[]; provenance?: MetricProvenance; compact?: boolean; wide?: boolean; footer?: React.ReactNode }>) {
  const { open } = useProvenance();
  // footer sits outside the role="img" canvas below - interactive controls
  // (e.g. pagination) inside an image-role region are invisible/inert to
  // assistive tech, so they can't live alongside the chart itself.
  return <article className={`insight-chart-card${compact ? " insight-chart-card--compact" : ""}${wide ? " insight-chart-card--wide" : ""}`}><header><div><h2>{title}</h2><p>{subtitle}</p></div><BasisBadge basis={basis} onClick={() => open(provenance ?? { code: `chart_${title}`, label: title, basis, value: null, explanation: subtitle, source_refs: sourceRefs })}/></header><div className="insight-chart-card__canvas" role="img" aria-label={`${title}. ${subtitle}`}>{children}</div>{footer ? <div className="insight-chart-card__footer">{footer}</div> : null}</article>;
}

export function Donut({ data, language, valueKind = "kzt", height = 270, minAngle = 0, colorFor }: { data: Array<{ name: string; value: number }>; language: Language; valueKind?: "kzt" | "number"; height?: number; minAngle?: number; colorFor?: (name: string, index: number) => string }) {
  // Recharts sorts legend entries alphabetically by default. Keep the
  // visual hierarchy instead: largest slices first, then smaller categories.
  const sortedData = [...data].sort((a, b) => b.value - a.value);
  return <ResponsiveContainer width="100%" height={height}>
    <PieChart>
      <Pie isAnimationActive={false} data={sortedData} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="82%" paddingAngle={2} minAngle={minAngle} cornerRadius={5} stroke="white" strokeWidth={2}>
        {sortedData.map((item, index) => <Cell key={`${item.name}-${index}`} fill={colorFor?.(item.name, index) ?? COLORS[index % COLORS.length]}/>)}
      </Pie>
      <Tooltip shared={false} content={<ChartTooltip language={language} valueKind={valueKind}/>}/>
      <Legend itemSorter={null} iconType="circle" verticalAlign="bottom" formatter={(value) => <span className="insight-chart-legend">{value}</span>}/>
    </PieChart>
  </ResponsiveContainer>;
}

export function ChartLegend({ items }: { items: Array<{ label: string; color: string }> }) {
  return <div className="insight-chart-fixed-legend" aria-label="Chart legend">{items.map((item) => <span key={item.label}><i style={{ background: item.color }} aria-hidden="true"/>{item.label}</span>)}</div>;
}

export function ChartTooltip({ active, payload, label, language, valueKind, labelKind, currencyField }: { active?: boolean; payload?: Array<{ name?: string; value?: unknown; color?: string; payload?: ChartDatum; dataKey?: string }>; label?: unknown; language: Language; valueKind: "kzt" | "number" | "percent"; labelKind?: "date"; currencyField?: string }) {
  if (!active || !payload?.length) return null;
  // A truncated axis category (see compactChartLabel on the concentration
  // chart) still needs its full name on hover - the row carries an
  // untruncated fullName alongside the truncated one used for the axis/label
  // when that distinction matters; charts without it just fall back to label.
  const displayLabel = payload[0]?.payload?.fullName ?? label;
  return <div className="insight-chart-tooltip">{displayLabel != null ? <strong>{labelKind === "date" ? formatDate(String(displayLabel), language) : String(displayLabel)}</strong> : null}{payload.map((item, index) => {
    const currency = currencyField ? String(item.payload?.[currencyField] ?? label ?? "").trim() : "";
    // Bars plotted on a log axis carry a "<field>Log" dataKey (see the
    // brokerage turnover/trade-count charts) so the bar height itself is
    // log-transformed; the tooltip must still read the real value the log
    // was taken from, not the transformed plotting value.
    const dataKey = item.dataKey ? String(item.dataKey) : undefined;
    const realValue = dataKey?.endsWith("Log") ? item.payload?.[dataKey.slice(0, -3)] : item.value;
    const displayValue = currencyField ? formatCurrencyAmount(String(realValue ?? 0), currency, language)
      : valueKind === "kzt" ? formatKzt(String(realValue ?? 0), language)
      : valueKind === "percent" ? `${formatNumber(String((numeric(realValue) ?? 0) * 100), language)}%`
      : formatNumber(String(realValue ?? 0), language);
    return <div key={`${item.name}-${index}`}><span style={{ background: item.color ?? COLORS[index % COLORS.length] }}/><em>{item.name ?? "—"}</em><b>{displayValue}</b></div>;
  })}</div>;
}

export function ChartEmpty({ language }: { language: Language }) { return <div className="insight-chart-empty">{language === "en" ? "No supported published values for this chart" : "Для графика нет поддерживаемых опубликованных значений"}</div>; }
export function numeric(value: unknown): number | null { const number = Number(value); return value == null || value === "" || !Number.isFinite(number) ? null : number; }
// The accounting balance sheet / income statement / budget workbooks state
// every *_kzt figure in thousands of tenge (source header: "в тысячах
// тенге" / "в тыс тг") - unlike accounting_portfolio_detail's carrying_value_kzt,
// which the source states directly "в тенге" (full units). Scale the
// thousands-denominated fields up so every KZT figure on this page is the
// same real-world unit; the raw source tables/exports still show the
// untouched thousands values, since those mirror the source cell exactly.
export function numericThousands(value: unknown): number | null { const scaled = numeric(value); return scaled == null ? null : scaled * 1000; }
export function compact(value: unknown, language: Language): string { const number = numeric(value) ?? 0; return new Intl.NumberFormat(language === "en" ? "en-GB" : "ru-RU", { notation: "compact", maximumFractionDigits: 1 }).format(number); }
export function categoryAxisWidth(labels: string[], maxWidth = 260): number {
  // The y-axis category column was a fixed 260px sized for the longest
  // label this app ever shows (full legal entity names on the client
  // chart) - short labels like "БРК"/"КФУ" on the corporate-finance chart
  // then left most of that column empty. Size it to the actual longest
  // label in this chart's own data instead, within a sane range.
  const longest = labels.reduce((max, label) => Math.max(max, label.length), 0);
  return Math.min(maxWidth, Math.max(60, longest * 7.5 + 32));
}
export function compactChartLabel(value: string, maxLength: number): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength - 1).trimEnd()}…` : normalized;
}
export function logAxisDomain(values: Array<number | null | undefined>): [number, number] {
  // [0, "auto"] wastes most of the plot: it always starts the axis at
  // 10^0 = 1 even when every value is in the millions or billions, and
  // Recharts' own "auto" upper bound tends to round a full decade past the
  // real maximum (confirmed live - a ~230bn KZT max rendered a 1tn axis
  // ceiling). Pad half a decade either side of the real min/max instead, so
  // bars fill the plot while still leaving room to not touch the edges.
  const finite = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!finite.length) return [0, 1];
  return [Math.floor(Math.min(...finite) - 0.5), Math.ceil(Math.max(...finite) + 0.3)];
}
export function comparisonDomain(values: number[]): [number, "auto"] {
  const positive = values.filter((value) => Number.isFinite(value) && value > 0);
  if (positive.length < 2) return [0, "auto"];
  const minimum = Math.min(...positive);
  const maximum = Math.max(...positive);
  const spread = maximum - minimum;
  // Leave a small, data-relative cushion below the smaller bar, then round
  // the bound down to a clean 1/2/5×10^n step. This keeps the comparison
  // honest while making small differences visible instead of flattening both
  // bars against a zero baseline.
  const cushion = Math.max(spread * 0.25, maximum * 0.005);
  const step = niceStep(Math.max(spread, maximum * 0.01));
  const lower = Math.max(0, Math.floor((minimum - cushion) / step) * step);
  return [lower < minimum ? lower : Math.max(0, minimum - step), "auto"];
}
export function niceStep(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const exponent = Math.floor(Math.log10(value));
  const fraction = value / (10 ** exponent);
  const normalized = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return normalized * (10 ** exponent);
}
export function formatCurrencyAmount(value: string, currency: string, language: Language): string {
  const symbol = ({ KZT: "₸", USD: "$", EUR: "€", GBP: "£" } as Record<string, string>)[currency.toUpperCase()] ?? `${currency} `;
  return `${symbol}${formatNumber(value, language)}`;
}
export function shortDate(value: unknown, language: Language): string { const date = new Date(String(value)); return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat(language === "en" ? "en-GB" : "ru-RU", { day: "2-digit", month: "short" }).format(date); }
export function asObject(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
export function sourceRefsFromRecords(rows: Row[], language: Language): ProvenanceRef[] {
  const seen = new Set<string>();
  return rows.flatMap((row) => {
    const source = asObject(row.source);
    const rowNumber = Number(source.row_number ?? source.row);
    const workbookName = String(source.filename ?? source.workbook_name ?? "").trim();
    const sheetName = String(source.sheet_name ?? source.sheet ?? "").trim();
    if (!Number.isFinite(rowNumber) || !workbookName || !sheetName) return [];
    const ref: ProvenanceRef = {
      workbook_name: workbookName,
      sheet_name: sheetName,
      row_number: rowNumber,
      parser_version: String(source.parser_version ?? "—"),
      source_row_id: String(row.id ?? `${sheetName}:${rowNumber}`),
      source_column: typeof source.source_column === "number" ? source.source_column : null,
      source_column_letter: typeof source.source_column_letter === "string" ? source.source_column_letter : null,
      source_cell: typeof source.source_cell === "string" ? source.source_cell : null,
      source_header: typeof source.source_header === "string" ? source.source_header : null,
      source_kind: "row",
      note: language === "en" ? "Exact source row used by this calculation." : "Точная строка источника, использованная в расчёте.",
    };
    const key = [ref.workbook_name, ref.sheet_name, ref.row_number, ref.source_cell, ref.source_row_id].join("|");
    if (seen.has(key)) return [];
    seen.add(key);
    return [ref];
  });
}
export function objectValues(value: unknown): Array<{ name: string; value: number }> { return Object.entries(asObject(value)).map(([name, amount]) => ({ name, value: numeric(amount) ?? 0 })).filter((item) => item.value !== 0); }
export function countField(rows: Row[], field: string): Record<string, number> { const counts: Record<string, number> = {}; for (const row of rows) { const label = String(row[field] ?? "Не указано").trim() || "Не указано"; counts[label] = (counts[label] ?? 0) + 1; } return counts; }
export function countFieldFallback(rows: Row[], fields: string[]): Record<string, number> { const counts: Record<string, number> = {}; for (const row of rows) { const label = fields.map((field) => String(row[field] ?? "").trim()).find(Boolean) || "Не указано"; counts[label] = (counts[label] ?? 0) + 1; } return counts; }
export function collapseOthers(items: Array<{ name: string; value: number }>, otherLabel: string, maxVisible: number, keep: (name: string) => boolean = () => false): Array<{ name: string; value: number }> {
  const sorted = [...items].sort((a, b) => b.value - a.value);
  if (sorted.length <= maxVisible) return sorted;
  const pinned = sorted.filter((item) => keep(item.name));
  const candidates = sorted.filter((item) => !keep(item.name));
  const visible = candidates.slice(0, Math.max(0, maxVisible - pinned.length));
  const hidden = candidates.slice(visible.length);
  const otherValue = hidden.reduce((sum, item) => sum + item.value, 0);
  return [...pinned, ...visible, ...(otherValue > 0 ? [{ name: otherLabel, value: otherValue }] : [])].sort((a, b) => b.value - a.value);
}
export function groupValues(rows: Row[], labelKey: string, valueKey: string): Array<{ name: string; value: number }> { const grouped = new Map<string, number>(); for (const row of rows) { const label = String(row[labelKey] ?? "—"); const value = numeric(row[valueKey]); if (value != null) grouped.set(label, (grouped.get(label) ?? 0) + value); } return [...grouped].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, 8); }
export function countBy<T extends Record<string, string>>(rows: T[], key: keyof T): Array<{ name: string; value: number }> { const counts = new Map<string, number>(); for (const row of rows) counts.set(row[key], (counts.get(row[key]) ?? 0) + 1); return [...counts].map(([name, value]) => ({ name, value })); }
export function isBuy(value: unknown): boolean { const text = String(value ?? "").trim().toLocaleLowerCase(); return text.startsWith("куп") || text.startsWith("покуп") || text.startsWith("buy"); }
export function isSell(value: unknown): boolean { const text = String(value ?? "").trim().toLocaleLowerCase(); return text.startsWith("прод") || text.startsWith("sell"); }
export function isRepoTrade(row: Row): boolean { if (row.is_repo === true) return true; return ["security_type", "instrument", "instrument_type", "trade_type", "deal_type", "transaction_type", "counterparty"].some((key) => { const text = String(row[key] ?? "").trim().toLocaleLowerCase(); return text.includes("репо") || /\brepo\b/.test(text); }); }
// Mirrors the keyword classification the backend already uses for OSIP
// holdings (_normalized_asset_class) so "stocks vs bonds" means the same
// thing across the app. security_type is free text from the source
// workbook (16+ distinct values seen in practice: "ГЦБ", "Евроноты", "GDR",
// "Купонные облигации", ...), so this can't be a fixed lookup table -
// matched by keyword instead, same as the backend does for "облигац"/"акци".
// Depositary receipts (GDR/ADR) represent equity ownership, so they count
// as stocks; funds/index products (ETF, Пай, Индекс) are neither and stay
// in "Прочее" rather than being guessed into one bucket or the other.
export function securityClassBucket(securityType: string, l: (ru: string, en: string) => string): string {
  const type = securityType.trim().toLocaleLowerCase();
  if (type.includes("облигац") || type.includes("гцб") || type.includes("евронот")) return l("Облигации", "Bonds");
  if (type.includes("акци") || type.includes("gdr") || type.includes("adr")) return l("Акции", "Stocks");
  return l("Прочее", "Other");
}
// Trade amounts are each in their own currency; summing them by security
// class needs a real KZT rate, not a guess. fxRatesKzt comes from the
// module summary (server-computed via the same NBK-rate resolver the Excel
// export uses - see services/multi_source.py). A currency with no resolved
// rate is left out of the total rather than fabricating one; the caller
// surfaces which currencies were skipped.
export function sumSecurityClassKzt(rows: Row[], fxRatesKzt: Record<string, string>, l: (ru: string, en: string) => string): Array<{ name: string; value: number }> {
  const totals: Record<string, number> = {};
  for (const row of rows) {
    const securityType = String(row.security_type ?? row.instrument_type ?? "").trim();
    const currency = String(row.currency ?? "").trim();
    const rate = fxRatesKzt[currency];
    const amount = numeric(row.amount);
    if (!securityType || !currency || rate === undefined || amount == null) continue;
    const bucket = securityClassBucket(securityType, l);
    totals[bucket] = (totals[bucket] ?? 0) + Math.abs(amount) * Number(rate);
  }
  return Object.entries(totals).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
}
export function stockBondColor(name: string): string {
  if (name === "Облигации" || name === "Bonds") return "#3d6fd8";
  if (name === "Акции" || name === "Stocks") return "#27a36a";
  return "#7b67c8";
}
export function executionVenueColor(name: string, index: number): string {
  const normalized = name.trim().toLocaleLowerCase();
  if (normalized === "other" || normalized === "прочие") return "#7b67c8";
  if (normalized.includes("неорганизован") || normalized.includes("unorgan")) return "#cf4253";
  return COLORS[index % COLORS.length];
}
