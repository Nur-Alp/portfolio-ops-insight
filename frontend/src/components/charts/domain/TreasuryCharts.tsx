import { BarChart, Bar, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ModuleReadResponse } from "../../../api/types";
import { ChartCard, ChartEmpty, ChartGrid, ChartTooltip, Donut, COLORS, GRID, axisTick, comparisonDomain, compact, numeric, type Language, type MetricProvenance, type ProvenanceRef } from "./shared";

export function TreasuryCharts({ data, language, sourceRefs = [], treasuryMetrics }: { data: ModuleReadResponse; language: Language; sourceRefs?: ProvenanceRef[]; treasuryMetrics?: Record<string, MetricProvenance> }) {
  const summaries = data.summaries as Record<string, Record<string, unknown>>;
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const summary = summaries.portfolio_snapshot ?? {};
  const valuation = [{ label: l("Портфель", "Portfolio"), purchase: numeric(summary.purchase_amount_kzt) ?? 0, carrying: numeric(summary.derived_carrying_value_kzt) ?? 0 }];
  const valuationDomain = comparisonDomain([valuation[0].purchase, valuation[0].carrying]);
  const composition = [
    { name: l("Расчётная стоимость", "Derived carrying value"), value: numeric(summary.derived_carrying_value_kzt) ?? 0 },
    { name: l("Деньги", "Cash"), value: numeric(summary.cash_kzt) ?? 0 }
  ].filter((item) => item.value !== 0);
  const valuationProvenance = treasuryMetrics ? {
    code: "treasury_valuation_basis_comparison",
    label: l("Сопоставление основ оценки", "Valuation-basis comparison"),
    basis: "derived" as const,
    value: null,
    formula: l("Сопоставляются Σ суммы покупки в KZT и Σ расчётной балансовой стоимости. Расчётная стоимость по лоту: AA × AU × AT + AR.", "Compares Σ purchase amount in KZT with Σ derived carrying value. Per-lot derived carrying value: AA × AU × AT + AR."),
    explanation: l("График использует точные входы двух показателей ниже; это сопоставление, а не официальный NAV.", "The chart uses the exact inputs of the two metrics below; it is a comparison, not official NAV."),
    source_refs: [...(treasuryMetrics.purchase_amount_kzt?.source_refs ?? []), ...(treasuryMetrics.derived_carrying_value_kzt?.source_refs ?? [])],
    inputs: [treasuryMetrics.purchase_amount_kzt, treasuryMetrics.derived_carrying_value_kzt].filter((metric): metric is MetricProvenance => Boolean(metric)).map((metric) => ({ code: metric.code, label: metric.label, value: metric.value, basis: metric.basis, source_refs: metric.source_refs })),
  } : undefined;
  return <ChartGrid>
    <ChartCard title={l("Сопоставление основ оценки", "Valuation-basis comparison")} subtitle={l("Покупная сумма из источника и расчётная балансовая стоимость — не официальный NAV. Ось начинается с округлённой нижней границы для наглядного сравнения.", "Source purchase amount versus derived carrying value; neither is official NAV. The axis starts at a rounded lower bound to make the comparison readable.")} basis="derived" sourceRefs={sourceRefs} provenance={valuationProvenance}>
      <ResponsiveContainer width="100%" height={270}><BarChart data={valuation} margin={{ top: 18, right: 14, left: 4, bottom: 4 }}><CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false}/><XAxis dataKey="label" tick={axisTick}/><YAxis domain={valuationDomain} allowDataOverflow tickFormatter={(value) => compact(value, language)} tick={axisTick} width={68}/><Tooltip content={<ChartTooltip language={language} valueKind="kzt"/>}/><Legend iconType="circle"/><Bar isAnimationActive={false} dataKey="purchase" name={l("Сумма покупки", "Purchase amount")} fill={COLORS[1]} radius={[6, 6, 0, 0]}/><Bar isAnimationActive={false} dataKey="carrying" name={l("Расчётная стоимость", "Derived carrying value")} fill={COLORS[0]} radius={[6, 6, 0, 0]}/></BarChart></ResponsiveContainer>
    </ChartCard>
    <ChartCard title={l("Операционный состав", "Operational composition")} subtitle={l("Расчётная стоимость плюс денежные средства; это не NAV и не рыночная стоимость.", "Derived carrying value plus cash; this is not NAV or market value.")} basis="derived" sourceRefs={sourceRefs} provenance={treasuryMetrics?.derived_operational_total_kzt}>
      {composition.length ? <Donut data={composition} language={language}/> : <ChartEmpty language={language}/>}
    </ChartCard>
  </ChartGrid>;
}
