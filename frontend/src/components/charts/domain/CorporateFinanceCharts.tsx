import { BarChart, Bar, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ModuleReadResponse } from "../../../api/types";
import {
  ChartCard, ChartGrid, ChartTooltip, axisTick, categoryAxisWidth, compact, logAxisDomain, numeric,
  sourceRefsFromRecords, COLORS, GRID, type Language, type ProvenanceRef, type Row,
} from "./shared";

export function CorporateFinanceCharts({ data, language, sourceRefs = [] }: { data: ModuleReadResponse; language: Language; sourceRefs?: ProvenanceRef[] }) {
  const records = data.records as Record<string, Row[]>;
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const sourceDeals = records.corporate_finance_register ?? [];
  const currencies = [...new Set(sourceDeals.flatMap((row) => [String(row.placement_currency ?? "").trim(), String(row.demand_currency ?? "").trim()]).filter(Boolean))];
  const MAX_ISSUER_ROWS = 12;
  const charts = currencies.map((currency) => {
    const allDeals = sourceDeals.map((row) => {
      const placement = String(row.placement_currency ?? "").trim() === currency ? numeric(row.placement_amount) : null;
      const demand = String(row.demand_currency ?? "").trim() === currency ? numeric(row.satisfied_demand) : null;
      // Issuers in the same currency can differ by two orders of magnitude
      // (e.g. a supranational's placement vs a single bank's) - on a linear
      // axis the smaller bars flatten to an invisible sliver next to the
      // largest one. Same fix as the brokerage turnover/trade-count charts:
      // log-transform for the bar height, keep the real amount for the
      // tooltip (see ChartTooltip's "Log"-suffix handling).
      return {
        row,
        name: String(row.issuer ?? "").trim() || String(row.subject ?? "").trim() || "—",
        placement, demand,
        placementLog: placement != null && placement > 0 ? Math.log10(placement) : null,
        demandLog: demand != null && demand > 0 ? Math.log10(demand) : null,
      };
    }).filter((row) => row.placement != null || row.demand != null);
    // Rank by the larger of the two amounts before capping - a chart with
    // one row per issuer grows unreadable well before dozens of issuers
    // (confirmed live: past ~12 rows it no longer fits without scrolling,
    // defeating the point of a bar chart). The unranked source order used
    // to just take whichever 12 rows happened to come first, not the 12
    // largest - the full list stays available in the deals table below.
    const sortedDeals = [...allDeals].sort((a, b) => Math.max(b.placement ?? 0, b.demand ?? 0) - Math.max(a.placement ?? 0, a.demand ?? 0));
    const deals = sortedDeals.slice(0, MAX_ISSUER_ROWS);
    if (deals.length < 2) return null;
    const baseSubtitle = l("Суммы показаны отдельно по валюте; неоднозначные строки исключены из графика и остаются в DQ. Логарифмическая шкала показывает разные порядки величины.", "Amounts are separated by currency; ambiguous rows are excluded from the chart and remain in DQ. The logarithmic scale keeps different orders of magnitude visible.");
    const subtitle = sortedDeals.length > deals.length
      ? `${baseSubtitle} ${l(`Показаны топ-${deals.length} из ${sortedDeals.length} эмитентов по размеру сделки; полный список — в таблице ниже.`, `Showing the top ${deals.length} of ${sortedDeals.length} issuers by deal size; see the full table below.`)}`
      : baseSubtitle;
    const axisDomain = logAxisDomain(deals.flatMap((row) => [row.placementLog, row.demandLog]));
    return <ChartCard key={currency} title={`${l("Размещение и удовлетворённый спрос", "Placement and satisfied demand")} · ${currency}`} subtitle={subtitle} basis="source" sourceRefs={sourceRefsFromRecords(deals.map((item) => item.row), language)}>
      {/* Same long-issuer-name wrapping risk as the client asset chart
          above - a wider label column plus a taller row prevents adjacent
          wrapped labels from overlapping. */}
      <ResponsiveContainer width="100%" height={Math.max(280, deals.length * 80)}><BarChart data={deals} layout="vertical" margin={{ top: 18, right: 18, left: 24, bottom: 8 }}><CartesianGrid stroke={GRID} strokeDasharray="3 5" horizontal={false}/><XAxis type="number" domain={axisDomain} allowDataOverflow tickFormatter={(value) => compact(10 ** Number(value), language)} tick={axisTick}/><YAxis type="category" dataKey="name" tick={axisTick} width={categoryAxisWidth(deals.map((row) => row.name))} interval={0} padding={{ top: 10, bottom: 10 }}/><Tooltip content={<ChartTooltip language={language} valueKind="number"/>}/><Legend iconType="circle"/><Bar isAnimationActive={false} dataKey="placementLog" name={l("Объём размещения", "Placement amount")} fill={COLORS[0]} radius={[0, 6, 6, 0]}/><Bar isAnimationActive={false} dataKey="demandLog" name={l("Удовлетворённый спрос", "Satisfied demand")} fill={COLORS[1]} radius={[0, 6, 6, 0]}/></BarChart></ResponsiveContainer>
    </ChartCard>;
  }).filter(Boolean);
  return charts.length ? <ChartGrid single={charts.length === 1}>{charts}</ChartGrid> : null;
}
