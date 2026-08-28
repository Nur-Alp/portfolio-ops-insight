import { AreaChart, Area, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ModuleReadResponse } from "../../../api/types";
import { ChartCard, ChartEmpty, ChartGrid, ChartTooltip, Donut, COLORS, GRID, axisTick, compact, groupValues, numeric, shortDate, sourceRefsFromRecords, type Language, type ProvenanceRef, type Row } from "./shared";

export function FundCharts({ data, language, sourceRefs = [] }: { data: ModuleReadResponse; language: Language; sourceRefs?: ProvenanceRef[] }) {
  const records = data.records as Record<string, Row[]>;
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const unitObservations = (records.fund_unit_series ?? []).filter((row) => row.record_type === "unit_observation" && numeric(row.unit_value_kzt) != null);
  const history = unitObservations
    .map((row) => ({ date: String(row.date ?? ""), value: numeric(row.unit_value_kzt)! }))
    .sort((a, b) => a.date.localeCompare(b.date));
  const holdings = groupValues(records.fund_holdings ?? [], "instrument", "purchase_value_kzt");
  return <ChartGrid>
    <ChartCard title={l("Стоимость пая", "Unit value")} subtitle={l("Источник; изменение между датами показано без заявления официальной доходности.", "Source-reported values; changes between dates are shown without claiming official performance.")} basis="source" sourceRefs={sourceRefsFromRecords(unitObservations, language)}>
      {history.length ? <ResponsiveContainer width="100%" height={270}><AreaChart data={history} margin={{ top: 12, right: 14, left: 4, bottom: 4 }}><defs><linearGradient id="unitValueFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS[0]} stopOpacity={0.32}/><stop offset="100%" stopColor={COLORS[0]} stopOpacity={0.02}/></linearGradient></defs><CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false}/><XAxis dataKey="date" tickFormatter={(value) => shortDate(value, language)} tick={axisTick}/><YAxis tickFormatter={(value) => compact(value, language)} tick={axisTick} width={68}/><Tooltip content={<ChartTooltip language={language} valueKind="kzt" labelKind="date"/>}/><Area isAnimationActive={false} type="monotone" dataKey="value" name={l("Стоимость пая", "Unit value")} stroke={COLORS[0]} strokeWidth={3} fill="url(#unitValueFill)" activeDot={{ r: 6, fill: COLORS[0], stroke: "white", strokeWidth: 3 }}/></AreaChart></ResponsiveContainer> : <ChartEmpty language={language}/>}
    </ChartCard>
    <ChartCard title={l("Состав портфеля фонда", "Fund portfolio allocation")} subtitle={l("По покупной стоимости опубликованных позиций.", "By purchase value of published holdings.")} basis="source" sourceRefs={sourceRefsFromRecords(records.fund_holdings ?? [], language)}>
      {holdings.length ? <Donut data={holdings} language={language}/> : <ChartEmpty language={language}/>}
    </ChartCard>
  </ChartGrid>;
}
