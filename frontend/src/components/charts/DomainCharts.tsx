import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { ModuleReadResponse } from "../../api/types";
import { AccountingCharts } from "./domain/AccountingCharts";
import type { IncomeStatementPeriod } from "../../pages/domain-panels/AccountingPanels";
import { BrokerageCharts } from "./domain/BrokerageCharts";
import { ClientsCharts } from "./domain/ClientsCharts";
import { CorporateFinanceCharts } from "./domain/CorporateFinanceCharts";
import { FundCharts } from "./domain/FundCharts";
import { RiskCharts } from "./domain/RiskCharts";
import { ChartCard, ChartGrid, ChartTooltip, COLORS, GRID, axisTick, countBy, Donut, type Language, type MetricProvenance, type ProvenanceRef } from "./domain/shared";
import { TreasuryCharts } from "./domain/TreasuryCharts";

export type ChartDomain = "asset-management" | "treasury" | "brokerage" | "clients" | "corporate-finance" | "accounting" | "risk";

export function DomainCharts({ kind, data, language, sourceRefs = [], includeRepo = true, treasuryMetrics, incomeStatementPeriod = "quarter" }: { kind: ChartDomain; data: ModuleReadResponse; language: Language; sourceRefs?: ProvenanceRef[]; includeRepo?: boolean; treasuryMetrics?: Record<string, MetricProvenance>; incomeStatementPeriod?: IncomeStatementPeriod }) {
  if (kind === "asset-management") return <FundCharts data={data} language={language} sourceRefs={sourceRefs} />;
  if (kind === "treasury") return <TreasuryCharts data={data} language={language} sourceRefs={sourceRefs} treasuryMetrics={treasuryMetrics} />;
  if (kind === "brokerage") return <BrokerageCharts data={data} language={language} sourceRefs={sourceRefs} includeRepo={includeRepo} />;
  if (kind === "clients") return <ClientsCharts data={data} language={language} sourceRefs={sourceRefs} />;
  if (kind === "corporate-finance") return <CorporateFinanceCharts data={data} language={language} sourceRefs={sourceRefs} />;
  if (kind === "risk") return <RiskCharts data={data} language={language} sourceRefs={sourceRefs} />;
  if (kind === "accounting") return <AccountingCharts data={data} language={language} sourceRefs={sourceRefs} incomeStatementPeriod={incomeStatementPeriod} />;
  return null;
}

export function OperationsCharts({ datasets, language, sourceRefs = [] }: { datasets: Array<{ status: string; scope_code: string }>; language: Language; sourceRefs?: ProvenanceRef[] }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const statuses = countBy(datasets, "status");
  const scopes = countBy(datasets, "scope_code").sort((a, b) => b.value - a.value);
  if (!datasets.length) return null;
  // A single published status or one scope is already fully explained by
  // the KPI cards and readiness table. Avoid rendering charts that only show
  // one 100% slice or one bar with no useful comparison.
  const statusChart = statuses.length > 1 ? <ChartCard title={l("Статусы версий данных", "Dataset version status")} subtitle={l("Распределение независимо управляемых дочерних наборов.", "Distribution of independently controlled child datasets.")} basis="source" sourceRefs={sourceRefs}><Donut data={statuses} language={language} valueKind="number"/></ChartCard> : null;
  const scopeChart = scopes.length > 1 ? <ChartCard title={l("Покрытие по областям", "Coverage by data scope")} subtitle={l("Количество версий наборов в каждой области данных.", "Number of dataset versions in each data scope.")} basis="source" sourceRefs={sourceRefs}><ResponsiveContainer width="100%" height={270}><BarChart data={scopes} margin={{ top: 18, right: 14, left: 4, bottom: 4 }}><CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false}/><XAxis dataKey="name" tick={axisTick}/><YAxis allowDecimals={false} tick={axisTick} width={34}/><Tooltip content={<ChartTooltip language={language} valueKind="number"/>}/><Bar isAnimationActive={false} dataKey="value" name={l("Версии", "Versions")} fill={COLORS[0]} radius={[7, 7, 0, 0]}/></BarChart></ResponsiveContainer></ChartCard> : null;
  if (!statusChart && !scopeChart) return null;
  return <ChartGrid>{statusChart}{scopeChart}</ChartGrid>;
}
