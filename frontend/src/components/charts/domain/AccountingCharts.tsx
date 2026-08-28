import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { ModuleReadResponse } from "../../../api/types";
import { MONTH_FIELD_KEYS, MONTH_SHORT_LABELS, type IncomeStatementPeriod } from "../../../pages/domain-panels/AccountingPanels";
import {
  ChartCard, ChartGrid, ChartTooltip, COLORS, GRID, axisTick, categoryAxisWidth, compact, compactChartLabel,
  numericThousands, numeric, sourceRefsFromRecords, type Language, type ProvenanceRef, type Row,
} from "./shared";

export function AccountingCharts({ data, language, sourceRefs = [], incomeStatementPeriod = "quarter" }: { data: ModuleReadResponse; language: Language; sourceRefs?: ProvenanceRef[]; incomeStatementPeriod?: IncomeStatementPeriod }) {
  const records = data.records as Record<string, Row[]>;
  const summaries = data.summaries as Record<string, Record<string, unknown>>;
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const bs = summaries.accounting_balance_sheet ?? {};
  const liabilities = numericThousands(bs.total_liabilities_kzt);
  const equity = numericThousands(bs.total_equity_kzt);
  // The precomputed summary only ever stored the quarter figure - read
  // straight from the income-statement records instead, the same
  // quarter/YTD-toggleable lookup the KPI cards above this chart use, so
  // switching the toggle moves both together.
  const incomeStatementRecords = records.accounting_income_statement ?? [];
  // "Monthly" has no column on this dataset (see DomainPage.tsx's
  // domainCards for the same fallback) - these two charts fall back to the
  // quarter figure, but are skipped below in favor of the dedicated
  // monthly-budget charts when that mode is active.
  const incomeStatementField = incomeStatementPeriod === "monthly" ? "quarter" : incomeStatementPeriod;
  const incomeField = `${incomeStatementField}_kzt`;
  const priorIncomeField = `prior_${incomeStatementField}_kzt`;
  const totalByLabelField = (label: string, field: string): number | null => {
    for (const row of incomeStatementRecords) {
      if (String(row.line_label ?? "").trim().toLocaleLowerCase() !== label) continue;
      const value = row[field];
      if (value !== null && value !== undefined && value !== "") return numericThousands(value);
    }
    return null;
  };
  const totalByLabel = (label: string): number | null => totalByLabelField(label, incomeField);
  const income = totalByLabel("итого доходов");
  const expenses = totalByLabel("итого расходов");
  const netProfit = totalByLabel("чистая прибыль (убыток) до уплаты корпоративного подоходного налога");
  const priorIncome = totalByLabelField("итого доходов", priorIncomeField);
  const priorExpenses = totalByLabelField("итого расходов", priorIncomeField);
  const priorNetProfit = totalByLabelField("чистая прибыль (убыток) до уплаты корпоративного подоходного налога", priorIncomeField);
  const incomeChartSourceRows = incomeStatementRecords.filter((row) => ["итого доходов", "итого расходов", "чистая прибыль (убыток) до уплаты корпоративного подоходного налога"].includes(String(row.line_label ?? "").trim().toLocaleLowerCase()));
  const periodLabel = incomeStatementPeriod === "ytd" ? l("С начала года", "Year to date") : l("За квартал", "Quarter");
  const priorPeriodLabel = incomeStatementPeriod === "ytd" ? l("С начала пред. года", "Prior-year YTD") : l("Аналог. квартал пред. года", "Prior-year quarter");
  const charts: React.ReactNode[] = [];
  if (liabilities != null && equity != null && (liabilities > 0 || equity > 0)) {
    const compositionRows = [
      { name: l("Обязательства", "Liabilities"), value: liabilities },
      { name: l("Капитал", "Equity"), value: equity },
    ];
    charts.push(
      <ChartCard key="balance" title={l("Состав баланса", "Balance sheet composition")} subtitle={l("Обязательства и капитал на конец отчётного периода.", "Liabilities and equity at the end of the reporting period.")} basis="source" sourceRefs={sourceRefsFromRecords(records.accounting_balance_sheet ?? [], language)}>
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie data={compositionRows} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} isAnimationActive={false}>
              {compositionRows.map((row, index) => <Cell key={row.name} fill={COLORS[index % COLORS.length]} />)}
            </Pie>
            <Tooltip content={<ChartTooltip language={language} valueKind="kzt" shareOfTotal={compositionRows.reduce((sum, row) => sum + row.value, 0)} />} />
            <Legend iconType="circle" />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>
    );
  }
  if (incomeStatementPeriod !== "monthly" && income != null && expenses != null && netProfit != null) {
    const flowRows = [{ name: periodLabel, income, expenses, netProfit }];
    charts.push(
      <ChartCard key="income" title={l("Доходы, расходы и чистая прибыль", "Income, expenses and net profit")} subtitle={incomeStatementPeriod === "ytd" ? l("С начала года, до уплаты корпоративного подоходного налога.", "Year to date, before corporate income tax.") : l("За отчётный квартал, до уплаты корпоративного подоходного налога.", "For the reporting quarter, before corporate income tax.")} basis="source" sourceRefs={sourceRefsFromRecords(incomeChartSourceRows, language)}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={flowRows} margin={{ top: 18, right: 18, left: 24, bottom: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="name" tick={axisTick} />
            <YAxis tick={axisTick} tickFormatter={(value) => compact(value, language)} />
            <Tooltip content={<ChartTooltip language={language} valueKind="kzt" />} />
            <Legend iconType="circle" />
            <Bar isAnimationActive={false} dataKey="income" name={l("Доходы", "Income")} fill={COLORS[2]} radius={[6, 6, 0, 0]} />
            <Bar isAnimationActive={false} dataKey="expenses" name={l("Расходы", "Expenses")} fill={COLORS[4]} radius={[6, 6, 0, 0]} />
            <Bar isAnimationActive={false} dataKey="netProfit" name={l("Чистая прибыль", "Net profit")} fill={COLORS[1]} radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    );
  }
  if (incomeStatementPeriod !== "monthly" && income != null && expenses != null && netProfit != null && priorIncome != null && priorExpenses != null && priorNetProfit != null) {
    // Same three lines as the chart above, but compared against the same
    // window a year earlier instead of against each other - which prior
    // window that is follows the toggle: a year-ago quarter for "Quarter",
    // a year-ago YTD for "YTD", never mixed.
    const yoyPeriodRows = [
      { name: l("Доходы", "Income"), current: income, prior: priorIncome },
      { name: l("Расходы", "Expenses"), current: expenses, prior: priorExpenses },
      { name: l("Чистая прибыль", "Net profit"), current: netProfit, prior: priorNetProfit },
    ];
    charts.push(
      <ChartCard key="income-yoy" title={`${l("Доходы, расходы и чистая прибыль", "Income, expenses and net profit")}: ${l("год к году", "year over year")}`} subtitle={incomeStatementPeriod === "ytd" ? l("С начала года против того же периода прошлого года.", "Year to date against the same period last year.") : l("Отчётный квартал против аналогичного квартала прошлого года.", "The reporting quarter against the same quarter last year.")} basis="source" sourceRefs={sourceRefsFromRecords(incomeChartSourceRows, language)}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={yoyPeriodRows} margin={{ top: 18, right: 18, left: 24, bottom: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="name" tick={axisTick} />
            <YAxis tick={axisTick} tickFormatter={(value) => compact(value, language)} />
            <Tooltip content={<ChartTooltip language={language} valueKind="kzt" />} />
            <Legend iconType="circle" />
            <Bar isAnimationActive={false} dataKey="prior" name={priorPeriodLabel} fill={COLORS[0]} radius={[6, 6, 0, 0]} />
            <Bar isAnimationActive={false} dataKey="current" name={periodLabel} fill={COLORS[1]} radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    );
  }
  const budgetRows = (records.accounting_budget ?? [])
    .filter((row) => row.section === "income_statement" && numericThousands(row.deviation_kzt) != null)
    .map((row) => ({
      row,
      name: compactChartLabel(String(row.line_label ?? ""), 22),
      fullName: String(row.line_label ?? ""),
      deviation: numericThousands(row.deviation_kzt)!,
      budget: numericThousands(row.budget_2025_kzt) ?? 0,
      actual: numericThousands(row.forecast_2025_kzt) ?? 0,
    }))
    .sort((a, b) => Math.abs(b.deviation) - Math.abs(a.deviation))
    .slice(0, 12);
  if (incomeStatementPeriod !== "monthly" && budgetRows.length >= 2) {
    charts.push(
      <ChartCard key="budget-variance" title={l("Исполнение бюджета 2025: план и факт (доходы/расходы)", "2025 budget execution: plan vs. actual (income/expenses)")} subtitle={l("Бюджет 2025 и прогнозный факт 2025 по крупнейшим по отклонению строкам; данных за 2026 год в бюджетной книге пока нет.", "2025 budget and 2025 forecast actual for the largest-deviation lines; the budget workbook has no 2026 data yet.")} basis="source" sourceRefs={sourceRefsFromRecords(budgetRows.map((item) => item.row), language)}>
        <ResponsiveContainer width="100%" height={Math.max(240, budgetRows.length * 44)}>
          <BarChart data={budgetRows} layout="vertical" margin={{ top: 18, right: 10, left: 4, bottom: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 5" horizontal={false} />
            <XAxis type="number" tickFormatter={(value) => compact(value, language)} tick={axisTick} />
            <YAxis type="category" dataKey="name" tick={axisTick} width={categoryAxisWidth(budgetRows.map((row) => row.name), 150)} interval={0} padding={{ top: 10, bottom: 10 }} />
            <Tooltip content={<ChartTooltip language={language} valueKind="kzt" />} />
            <Legend iconType="circle" />
            <Bar isAnimationActive={false} dataKey="budget" name={l("Бюджет 2025", "2025 budget")} fill={COLORS[0]} radius={[0, 4, 4, 0]} />
            <Bar isAnimationActive={false} dataKey="actual" name={l("Прогнозный факт 2025", "2025 forecast actual")} fill={COLORS[2]} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    );
  }
  // Gross figures dropped in favor of their net counterpart, which already
  // covers the same underlying activity - keeping both would waste two of
  // the five slots on one concept: "Комиссионные доходы" duplicates
  // "Чистый комиссионный доход" (gross vs net commission), and
  // "Процентные доходы" duplicates "Чистый процентный доход" (gross vs net
  // of interest expense). Neither currently lands in the top 5 alongside
  // its net counterpart, but excluding both preemptively means a future
  // workbook's numbers can't quietly reintroduce the same collision.
  const MONTHLY_TREND_EXCLUDED_LINES = new Set(["Комиссионные доходы", "Процентные доходы"]);
  const monthlyTrendCandidates = (records.accounting_budget ?? [])
    .filter((row) => row.section === "income_statement" && !MONTHLY_TREND_EXCLUDED_LINES.has(String(row.line_label ?? "")))
    .map((row, index) => ({
      row,
      key: `${compactChartLabel(String(row.line_label ?? ""), 34)}#${index}`,
      name: compactChartLabel(String(row.line_label ?? ""), 34),
      deviation: Math.abs(numericThousands(row.deviation_kzt) ?? 0),
      oct: numericThousands(row.oct_2025_kzt),
      nov: numericThousands(row.nov_2025_kzt),
      dec: numericThousands(row.dec_2025_kzt),
    }))
    .filter((row) => row.oct != null || row.nov != null || row.dec != null)
    .sort((a, b) => b.deviation - a.deviation);
  // Some lines (e.g. pre-tax vs. net profit, when this quarter's tax is
  // zero) carry the exact same Oct/Nov/Dec figures - two lines plotted on
  // identical points draw as one, so the second, lower one, is invisible
  // on the chart despite having its own legend entry. Skip any candidate
  // whose full monthly series exactly matches one already picked.
  const seenSeries = new Set<string>();
  const monthlyTrendLines: typeof monthlyTrendCandidates = [];
  for (const candidate of monthlyTrendCandidates) {
    const fingerprint = `${candidate.oct}|${candidate.nov}|${candidate.dec}`;
    if (seenSeries.has(fingerprint)) continue;
    seenSeries.add(fingerprint);
    monthlyTrendLines.push(candidate);
    if (monthlyTrendLines.length === 5) break;
  }
  if (monthlyTrendLines.length >= 2) {
    // Keep a genuinely missing month as null, not 0 - a line with a real
    // reported zero and a line with no source figure for that month must
    // not render identically. Recharts leaves a gap for a null point
    // (default connectNulls=false) instead of drawing a fabricated dip.
    const monthlyTrendData = [
      { name: l("Окт", "Oct"), ...Object.fromEntries(monthlyTrendLines.map((row) => [row.key, row.oct])) },
      { name: l("Ноя", "Nov"), ...Object.fromEntries(monthlyTrendLines.map((row) => [row.key, row.nov])) },
      { name: l("Дек", "Dec"), ...Object.fromEntries(monthlyTrendLines.map((row) => [row.key, row.dec])) },
    ];
    charts.push(
      <ChartCard key="monthly-trend" title={l("Динамика по месяцам (Окт-Дек 2025)", "Monthly trend (Oct-Dec 2025)")} subtitle={l("Крупнейшие по отклонению строки бюджета за последний квартал года; лист «Бюджет» бюджетной рабочей книги, компактный блок «Октябрь-Ноябрь-Декабрь».", "Largest-deviation budget lines over the year's final quarter; from the “Бюджет” sheet of the budget workbook, the compact “October-November-December” block.")} basis="source" sourceRefs={sourceRefsFromRecords(monthlyTrendLines.map((item) => item.row), language)}>
        <ResponsiveContainer width="100%" height={420}>
          <LineChart data={monthlyTrendData} margin={{ top: 18, right: 18, left: 24, bottom: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="name" tick={axisTick} />
            <YAxis tick={axisTick} tickFormatter={(value) => compact(value, language)} />
            <Tooltip content={<ChartTooltip language={language} valueKind="kzt" />} />
            <Legend iconType="circle" formatter={(value) => <span>{String(value).replace(/#\d+$/, "")}</span>} />
            {monthlyTrendLines.map((row, index) => (
              <Line key={row.key} isAnimationActive={false} type="monotone" dataKey={row.key} name={row.key} stroke={COLORS[index % COLORS.length]} strokeWidth={2.5} dot={{ r: 3 }} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
    );
  }
  const cashFlowRows = (records.accounting_budget ?? [])
    .filter((row) => row.section === "cash_flow" && numericThousands(row.deviation_kzt) != null)
    .map((row) => ({
      row,
      name: compactChartLabel(String(row.line_label ?? ""), 22),
      fullName: String(row.line_label ?? ""),
      deviation: numericThousands(row.deviation_kzt)!,
      budget: numericThousands(row.budget_2025_kzt) ?? 0,
      actual: numericThousands(row.forecast_2025_kzt) ?? 0,
    }))
    .sort((a, b) => Math.abs(b.deviation) - Math.abs(a.deviation))
    .slice(0, 12);
  if (cashFlowRows.length >= 2) {
    charts.push(
      <ChartCard key="cash-flow-variance" title={l("Исполнение бюджета 2025: план и факт (движение денежных средств)", "2025 budget execution: plan vs. actual (cash flow)")} subtitle={l("Бюджет 2025 и прогнозный факт 2025 по крупнейшим по отклонению строкам раздела движения денежных средств.", "2025 budget and 2025 forecast actual for the largest-deviation cash-flow lines.")} basis="source" sourceRefs={sourceRefsFromRecords(cashFlowRows.map((item) => item.row), language)}>
        <ResponsiveContainer width="100%" height={Math.max(240, cashFlowRows.length * 44)}>
          <BarChart data={cashFlowRows} layout="vertical" margin={{ top: 18, right: 10, left: 4, bottom: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 5" horizontal={false} />
            <XAxis type="number" tickFormatter={(value) => compact(value, language)} tick={axisTick} />
            <YAxis type="category" dataKey="name" tick={axisTick} width={categoryAxisWidth(cashFlowRows.map((row) => row.name), 150)} interval={0} padding={{ top: 10, bottom: 10 }} />
            <Tooltip content={<ChartTooltip language={language} valueKind="kzt" />} />
            <Legend iconType="circle" />
            <Bar isAnimationActive={false} dataKey="budget" name={l("Бюджет 2025", "2025 budget")} fill={COLORS[0]} radius={[0, 4, 4, 0]} />
            <Bar isAnimationActive={false} dataKey="actual" name={l("Прогнозный факт 2025", "2025 forecast actual")} fill={COLORS[2]} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    );
  }
  // 2025 dropped from this comparison: the source only gives full-year
  // totals for 2023/2024, while 2025's only available figure
  // (forecast_2025_kzt) mixes actual months with projected ones - keeping
  // it here would put a partially-projected bar next to two purely actual
  // ones with no way to flag which was which. Year-over-year stays
  // actual-only; see the separate "Исполнение бюджета" chart for a plan
  // vs. forecast view that's explicit about being a forecast.
  const yoyRows = (records.accounting_budget ?? [])
    .filter((row) => row.section === "income_statement")
    .map((row) => {
      const y2023 = numericThousands(row.year_2023_kzt);
      const y2024 = numericThousands(row.year_2024_kzt);
      const magnitude = Math.max(Math.abs(y2023 ?? 0), Math.abs(y2024 ?? 0));
      return { row, name: compactChartLabel(String(row.line_label ?? ""), 22), fullName: String(row.line_label ?? ""), y2023, y2024, magnitude };
    })
    .filter((row) => row.y2023 != null && row.y2024 != null)
    .sort((a, b) => b.magnitude - a.magnitude)
    .slice(0, 6);
  if (incomeStatementPeriod !== "monthly" && yoyRows.length >= 2) {
    charts.push(
      <ChartCard key="yoy-trend" title={l("Динамика по годам, 2023-2024", "Year-over-year trend, 2023-2024")} subtitle={l("Крупнейшие строки бюджета по абсолютному значению за два полных отчётных года.", "Largest budget lines by absolute value across two full reporting years.")} basis="source" sourceRefs={sourceRefsFromRecords(yoyRows.map((item) => item.row), language)}>
        <ResponsiveContainer width="100%" height={Math.max(260, yoyRows.length * 40)}>
          <BarChart data={yoyRows} layout="vertical" margin={{ top: 18, right: 10, left: 4, bottom: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 5" horizontal={false} />
            <XAxis type="number" tickFormatter={(value) => compact(value, language)} tick={axisTick} />
            <YAxis type="category" dataKey="name" tick={axisTick} width={categoryAxisWidth(yoyRows.map((row) => row.name), 150)} interval={0} padding={{ top: 10, bottom: 10 }} />
            <Tooltip content={<ChartTooltip language={language} valueKind="kzt" />} />
            <Legend iconType="circle" />
            <Bar isAnimationActive={false} dataKey="y2023" name="2023" fill={COLORS[0]} radius={[0, 4, 4, 0]} />
            <Bar isAnimationActive={false} dataKey="y2024" name="2024" fill={COLORS[1]} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    );
  }
  if (incomeStatementPeriod === "monthly") {
    const monthNames = MONTH_SHORT_LABELS.map(([ru, en]) => l(ru, en));
    const monthlySeries = (section: string, label: string): { row: Row; values: Array<number | null> } | null => {
      const row = (records.accounting_budget ?? []).find((candidate) => candidate.section === section && String(candidate.line_label ?? "").trim().toLocaleLowerCase() === label);
      if (!row) return null;
      const values = MONTH_FIELD_KEYS.map((field) => numericThousands(row[field]));
      return values.some((value) => value != null) ? { row, values } : null;
    };
    const netProfitMonthly = monthlySeries("income_statement", "чистая прибыль");
    if (netProfitMonthly) {
      const rows = monthNames.map((name, index) => ({ name, netProfit: netProfitMonthly.values[index] }));
      charts.push(
        <ChartCard key="monthly-income" title={l("Чистая прибыль по месяцам", "Net profit by month")} subtitle={l("Лист «Бюджет» бюджетной рабочей книги, раздел «Отчёт о прибылях и убытках», полная таблица «Январь-Декабрь».", "From the “Бюджет” sheet of the budget workbook, income-statement section, the full “January-December” table.")} basis="source" sourceRefs={sourceRefsFromRecords([netProfitMonthly.row], language)}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={rows} margin={{ top: 18, right: 18, left: 24, bottom: 8 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false} />
              <XAxis dataKey="name" tick={axisTick} />
              <YAxis tick={axisTick} tickFormatter={(value) => compact(value, language)} />
              <Tooltip content={<ChartTooltip language={language} valueKind="kzt" />} />
              <Line isAnimationActive={false} type="monotone" dataKey="netProfit" name={l("Чистая прибыль", "Net profit")} stroke={COLORS[1]} strokeWidth={2.5} dot={{ r: 3 }} connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      );
    }
    const cashEndMonthly = monthlySeries("cash_flow", "остаток дс на конец периода");
    if (cashEndMonthly) {
      const rows = monthNames.map((name, index) => ({ name, cash: cashEndMonthly.values[index] }));
      charts.push(
        <ChartCard key="monthly-cash" title={l("Остаток денежных средств по месяцам", "Cash balance by month")} subtitle={l("Остаток на конец периода; лист «Бюджет» бюджетной рабочей книги, раздел ДДС, полная таблица «Январь-Декабрь».", "Period-end balance; from the “Бюджет” sheet of the budget workbook, cash-flow section, the full “January-December” table.")} basis="source" sourceRefs={sourceRefsFromRecords([cashEndMonthly.row], language)}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={rows} margin={{ top: 18, right: 18, left: 24, bottom: 8 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false} />
              <XAxis dataKey="name" tick={axisTick} />
              <YAxis tick={axisTick} tickFormatter={(value) => compact(value, language)} />
              <Tooltip content={<ChartTooltip language={language} valueKind="kzt" />} />
              <Line isAnimationActive={false} type="monotone" dataKey="cash" name={l("Остаток ДС", "Cash balance")} stroke={COLORS[2]} strokeWidth={2.5} dot={{ r: 3 }} connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      );
    }
    const assetsMonthly = monthlySeries("balance", "итого активы");
    const liabilitiesMonthly = monthlySeries("balance", "итого обязательства");
    const equityMonthly = monthlySeries("balance", "итого собственный капитал");
    if (assetsMonthly || liabilitiesMonthly || equityMonthly) {
      const rows = monthNames.map((name, index) => ({
        name,
        assets: assetsMonthly?.values[index] ?? null,
        liabilities: liabilitiesMonthly?.values[index] ?? null,
        equity: equityMonthly?.values[index] ?? null,
      }));
      const balanceMonthlySourceRows = [assetsMonthly?.row, liabilitiesMonthly?.row, equityMonthly?.row].filter((row): row is Row => row != null);
      charts.push(
        <ChartCard key="monthly-balance" title={l("Баланс по месяцам", "Balance by month")} subtitle={l("Активы, обязательства и капитал на конец каждого месяца; лист «Бюджет» бюджетной рабочей книги, раздел «Баланс», полная таблица «Январь-Декабрь».", "Assets, liabilities and equity as of each month's end; from the “Бюджет” sheet of the budget workbook, balance section, the full “January-December” table.")} basis="source" sourceRefs={sourceRefsFromRecords(balanceMonthlySourceRows, language)}>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={rows} margin={{ top: 18, right: 18, left: 24, bottom: 8 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false} />
              <XAxis dataKey="name" tick={axisTick} />
              <YAxis tick={axisTick} tickFormatter={(value) => compact(value, language)} />
              <Tooltip content={<ChartTooltip language={language} valueKind="kzt" />} />
              <Legend iconType="circle" />
              {assetsMonthly ? <Line isAnimationActive={false} type="monotone" dataKey="assets" name={l("Активы", "Assets")} stroke={COLORS[0]} strokeWidth={2.5} dot={{ r: 3 }} connectNulls={false} /> : null}
              {liabilitiesMonthly ? <Line isAnimationActive={false} type="monotone" dataKey="liabilities" name={l("Обязательства", "Liabilities")} stroke={COLORS[3]} strokeWidth={2.5} dot={{ r: 3 }} connectNulls={false} /> : null}
              {equityMonthly ? <Line isAnimationActive={false} type="monotone" dataKey="equity" name={l("Капитал", "Equity")} stroke={COLORS[4]} strokeWidth={2.5} dot={{ r: 3 }} connectNulls={false} /> : null}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      );
    }
  }
  const portfolioByCategory = new Map<string, number>();
  for (const row of records.accounting_portfolio_detail ?? []) {
    const value = numeric(row.carrying_value_kzt);
    if (value == null) continue;
    const category = String(row.category ?? "");
    portfolioByCategory.set(category, (portfolioByCategory.get(category) ?? 0) + value);
  }
  const portfolioRows = [...portfolioByCategory.entries()].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  // Hidden by request - kept computed and ready to re-enable rather than
  // deleted, since the underlying data (accounting_portfolio_detail) is a
  // genuinely separate source/taxonomy from risk's instrument_category
  // concentration chart, not an actual duplicate.
  const SHOW_PORTFOLIO_BY_CATEGORY = false;
  if (SHOW_PORTFOLIO_BY_CATEGORY && portfolioRows.length >= 2) {
    charts.push(
      <ChartCard key="portfolio" title={l("Портфель по категориям инструментов", "Portfolio by instrument category")} subtitle={l("Балансовая стоимость по категории, из отдельного источника детализации портфеля.", "Carrying value by category, from the separate portfolio-detail source.")} basis="source" sourceRefs={sourceRefsFromRecords(records.accounting_portfolio_detail ?? [], language)}>
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie data={portfolioRows} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} isAnimationActive={false}>
              {portfolioRows.map((row, index) => <Cell key={row.name} fill={COLORS[index % COLORS.length]} />)}
            </Pie>
            <Tooltip content={<ChartTooltip language={language} valueKind="kzt" shareOfTotal={portfolioRows.reduce((sum, row) => sum + row.value, 0)} />} />
            <Legend iconType="circle" />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>
    );
  }
  // Swap the year-over-year income chart and the monthly trend chart's grid
  // position (by request) without relocating either chart's own build logic
  // above, which stays in its natural place next to the data it reads.
  const yoyChartIndex = charts.findIndex((chart) => (chart as React.ReactElement | null)?.key === "income-yoy");
  const monthlyTrendChartIndex = charts.findIndex((chart) => (chart as React.ReactElement | null)?.key === "monthly-trend");
  if (yoyChartIndex !== -1 && monthlyTrendChartIndex !== -1) {
    [charts[yoyChartIndex], charts[monthlyTrendChartIndex]] = [charts[monthlyTrendChartIndex], charts[yoyChartIndex]];
  }
  return charts.length ? <ChartGrid single={charts.length === 1}>{charts}</ChartGrid> : null;
}
