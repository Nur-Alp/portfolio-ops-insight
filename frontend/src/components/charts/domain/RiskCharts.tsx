import { useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  LabelList,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { ModuleReadResponse } from "../../../api/types";
import {
  ChartCard, ChartEmpty, ChartGrid, ChartLegend, ChartTooltip, COLORS, GRID, MUTED, axisTick, categoryAxisWidth,
  compact, compactChartLabel, numeric, shortDate, sourceRefsFromRecords, type Language, type ProvenanceRef, type Row,
} from "./shared";

export function RiskCharts({ data, language, sourceRefs = [] }: { data: ModuleReadResponse; language: Language; sourceRefs?: ProvenanceRef[] }) {
  const records = data.records as Record<string, Row[]>;
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  // Risk dimensions overlap (issuer, country, sector, etc.), so their
  // percentages must never be presented as one additive concentration total.
  const [riskConcentrationDimension, setRiskConcentrationDimension] = useState("issuer");
  const [riskConcentrationLimit, setRiskConcentrationLimit] = useState(8);
  const [riskConcentrationSharedScale, setRiskConcentrationSharedScale] = useState(true);
  const [riskUtilizationSeriesKey, setRiskUtilizationSeriesKey] = useState("");

  const rows = [...(records.risk_limits_sobstv ?? []), ...(records.risk_limits_tabys ?? [])];
  const dimensionLabels: Record<string, [string, string]> = {
    instrument_category: ["Класс инструментов", "Instrument category"],
    country: ["Страна", "Country"],
    issuer: ["Эмитент", "Issuer"],
    sector: ["Отрасль GICS", "GICS sector"],
    ifrs: ["Классификация МСФО", "IFRS classification"],
    currency: ["Валюта", "Currency"],
    fx_position: ["Открытая валютная позиция", "Open FX position"],
    instrument_issuer: ["Инструмент одного эмитента", "Instrument per issuer"],
    duration: ["Дюрация", "Duration"],
    exposure_detail: ["Детализация экспозиции", "Exposure detail"],
    country_instrument_detail: ["Детализация по странам", "Country detail"],
  };
  const detailOnlyDimensions = new Set(["exposure_detail", "country_instrument_detail"]);
  const byDimension = new Map<string, { ok: number; breach: number; unknown: number; not_applicable: number }>();
  for (const row of rows) {
    const dimension = String(row.dimension ?? "");
    // detailOnlyDimensions are always "no applicable limit" by
    // definition (informational rows, never a real limit control) - a
    // full-height grey bar here adds nothing a limit-status chart needs;
    // they're already excluded from the utilization dropdown below for
    // the same reason.
    if (detailOnlyDimensions.has(dimension)) continue;
    const bucket = byDimension.get(dimension) ?? { ok: 0, breach: 0, unknown: 0, not_applicable: 0 };
    const signal = String(row.signal ?? "unknown");
    if (signal === "breach") bucket.breach += 1;
    else if (signal === "not_applicable") bucket.not_applicable += 1;
    else if (signal === "unknown") bucket.unknown += 1;
    else bucket.ok += 1;
    byDimension.set(dimension, bucket);
  }
  const chartRows = [...byDimension.entries()]
    .map(([dimension, counts]) => {
      const fullName = dimensionLabels[dimension]?.[language === "en" ? 1 : 0] ?? dimension;
      // Now a half-width card (see the ChartGrid below) sharing its row with
      // the breach-trend chart - the longest label ("Инструмент одного
      // эмитента"/"Instrument per issuer") used to reserve a y-axis column
      // wide enough to fit it uncut, leaving every shorter label (most of
      // them) stranded in a mostly-empty gutter. Truncating it the same way
      // the concentration/duration charts below already do lets the axis
      // column - and therefore the plotted bars - actually use the width.
      return { name: compactChartLabel(fullName, 18), fullName, ok: counts.ok, breach: counts.breach, unknown: counts.unknown, not_applicable: counts.not_applicable };
    })
    .sort((a, b) => (b.ok + b.breach + b.unknown + b.not_applicable) - (a.ok + a.breach + a.unknown + a.not_applicable));
  const chartSourceRows = rows.filter((row) => !detailOnlyDimensions.has(String(row.dimension ?? "")));
  const history = ((data.history ?? []) as Array<{ business_date: string; breach_count: number; near_breach_count: number }>)
    .map((entry) => ({ date: entry.business_date, breach: entry.breach_count, near_breach: entry.near_breach_count }));
  const concentrationDimensionLabel = (dimension: string) => dimensionLabels[dimension]?.[language === "en" ? 1 : 0] ?? dimension;
  const utilizationObservations = ((data.risk_utilization_history ?? []) as Array<{ business_date: string; portfolio_code: string; dimension: string; label: string; utilization: string | number }>)
    .map((entry) => ({ ...entry, value: numeric(entry.utilization) }))
    .filter((entry): entry is { business_date: string; portfolio_code: string; dimension: string; label: string; utilization: string | number; value: number } => entry.value != null);
  const utilizationSeries = new Map<string, { key: string; label: string; rows: Array<{ date: string; utilization: number }> }>();
  for (const observation of utilizationObservations) {
    const key = [observation.portfolio_code, observation.dimension, observation.label].join("\u0000");
    const series = utilizationSeries.get(key) ?? {
      key,
      label: `${observation.portfolio_code} · ${concentrationDimensionLabel(observation.dimension)} · ${observation.label}`,
      rows: [],
    };
    series.rows.push({ date: observation.business_date, utilization: observation.value });
    utilizationSeries.set(key, series);
  }
  const comparableUtilizationSeries = [...utilizationSeries.values()]
    .filter((series) => new Set(series.rows.map((row) => row.date)).size >= 2)
    .map((series) => ({ ...series, rows: [...series.rows].sort((left, right) => left.date.localeCompare(right.date)) }))
    .sort((left, right) => right.rows.at(-1)!.utilization - left.rows.at(-1)!.utilization || left.label.localeCompare(right.label));
  const selectedUtilizationSeries = comparableUtilizationSeries.find((series) => series.key === riskUtilizationSeriesKey) ?? comparableUtilizationSeries[0];
  // "duration" is measured as modified duration against a duration limit
  // (see the ingestion payload for that dimension), never as limit
  // utilization - unlike the other dimensions excluded via
  // detailOnlyDimensions above, this isn't a per-dataset gap, so it's kept
  // out of this dropdown specifically rather than out of every risk chart
  // (its breach/ok signal is still meaningful on the other risk charts).
  const noUtilizationPctDimensions = new Set(["duration"]);
  const concentrationDimensions = [...new Set(rows
    .map((row) => String(row.dimension ?? ""))
    .filter((dimension) => dimension && !detailOnlyDimensions.has(dimension) && !noUtilizationPctDimensions.has(dimension)))]
    .sort((left, right) => concentrationDimensionLabel(left).localeCompare(concentrationDimensionLabel(right)));
  const selectedConcentrationDimension = concentrationDimensions.includes(riskConcentrationDimension)
    ? riskConcentrationDimension
    : concentrationDimensions[0] ?? "";
  // Plots the stored utilization field (actual/limit, base_label-aware -
  // see _risk_utilization in ingestion), not actual_pct directly. A row's
  // actual_pct alone is its share of the portfolio, not of its own limit;
  // dividing by a mismatched-base limit_pct produces nonsense for some
  // rows (confirmed on real data - a SOBSTV issuer at 86.2% of assets
  // against a 22.5%-of-capital limit is NOT 383% over), which is exactly
  // why this reads the same pre-computed, corrected field the export and
  // watchlist already use, rather than recomputing actual_pct/limit_pct here.
  const concentration = (["SOBSTV", "TABYS"] as const).map((portfolio) => {
    const eligible = rows.filter((row) => row.portfolio_code === portfolio && String(row.dimension ?? "") === selectedConcentrationDimension);
    const withUtilization = eligible.filter((row) => numeric(row.utilization) != null);
    const topSourceRows = [...withUtilization]
      .sort((a, b) => numeric(b.utilization)! - numeric(a.utilization)!)
      .slice(0, riskConcentrationLimit);
    const top = topSourceRows.map((row) => ({ name: compactChartLabel(String(row.label ?? ""), 20), fullName: String(row.label ?? ""), value: numeric(row.utilization)! * 100 }));
    return { portfolio, top, topSourceRows, excludedCount: eligible.length - withUtilization.length };
  });
  if (!chartRows.length) return null;
  const concentrationMax = Math.max(0, ...concentration.flatMap((item) => item.top.map((row) => row.value)));
  const concentrationDomain = riskConcentrationSharedScale
    ? [0, Math.max(100, Math.ceil(concentrationMax / 10) * 10)] as [number, number]
    : undefined;
  const baseChartCount = 1 + (history.length >= 2 ? 1 : 0) + (selectedUtilizationSeries ? 1 : 0);
  return <>
    <ChartGrid single={baseChartCount < 2}>
    <ChartCard
      title={l("Лимитные строки по измерению", "Limit lines by dimension")}
      subtitle={l("В пределах лимита, превышения, неопределённые и информационные строки по каждому измерению для обоих портфелей.", "Within-limit, breached, unresolved, and informational lines by dimension across both portfolios.")}
      basis="source" sourceRefs={sourceRefsFromRecords(chartSourceRows, language)}
      footer={<ChartLegend items={[
        { label: l("В пределах лимита", "Within limit"), color: COLORS[2] },
        { label: l("Превышение", "Breach"), color: COLORS[4] },
        { label: l("Статус не определён", "Status unknown"), color: COLORS[3] },
        { label: l("Без применимого лимита", "No applicable limit"), color: MUTED },
      ]}/>}
    >
      <div className="insight-chart-scroll" role="region" style={{ height: Math.min(300, Math.max(220, chartRows.length * 60)) }} tabIndex={0} aria-label={l("Прокручиваемая область графика", "Scrollable chart area")}>
        <div className="insight-chart-scroll__content" style={{ height: Math.max(220, chartRows.length * 60) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartRows} layout="vertical" margin={{ top: 18, right: 18, left: 24, bottom: 8 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="3 5" horizontal={false}/>
              <XAxis type="number" allowDecimals={false} tick={axisTick}/>
              <YAxis type="category" dataKey="name" tick={axisTick} width={categoryAxisWidth(chartRows.map((row) => row.name), 150)} interval={0} padding={{ top: 10, bottom: 10 }}/>
              <Tooltip content={<ChartTooltip language={language} valueKind="number"/>}/>
              <Bar isAnimationActive={false} dataKey="ok" stackId="limits" name={l("В пределах лимита", "Within limit")} fill={COLORS[2]} radius={[0, 0, 0, 0]}/>
              <Bar isAnimationActive={false} dataKey="breach" stackId="limits" name={l("Превышение", "Breach")} fill={COLORS[4]} radius={[0, 6, 6, 0]}/>
              <Bar isAnimationActive={false} dataKey="unknown" stackId="limits" name={l("Статус не определён", "Status unknown")} fill={COLORS[3]} radius={[0, 0, 0, 0]}/>
              <Bar isAnimationActive={false} dataKey="not_applicable" stackId="limits" name={l("Без применимого лимита", "No applicable limit")} fill={MUTED} radius={[0, 6, 6, 0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </ChartCard>
    {history.length >= 2 ? <ChartCard
      title={l("Динамика превышений", "Breach trend")}
      subtitle={l("Число превышений и близких к превышению строк по датам публикации, оба портфеля вместе.", "Breach and near-breach line counts by published business date, both portfolios combined.")}
      basis="source" sourceRefs={sourceRefs}
    >
      <ResponsiveContainer width="100%" height={270}>
        <AreaChart data={history} margin={{ top: 12, right: 14, left: 4, bottom: 4 }}>
          <defs>
            <linearGradient id="riskBreachFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS[4]} stopOpacity={0.32}/><stop offset="100%" stopColor={COLORS[4]} stopOpacity={0.02}/></linearGradient>
            <linearGradient id="riskNearBreachFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS[3]} stopOpacity={0.28}/><stop offset="100%" stopColor={COLORS[3]} stopOpacity={0.02}/></linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false}/>
          <XAxis dataKey="date" tickFormatter={(value) => shortDate(value, language)} tick={axisTick}/>
          <YAxis allowDecimals={false} tick={axisTick} width={40}/>
          <Tooltip content={<ChartTooltip language={language} valueKind="number" labelKind="date"/>}/>
          <Legend iconType="circle"/>
          <Area isAnimationActive={false} type="monotone" dataKey="breach" name={l("Превышение", "Breach")} stroke={COLORS[4]} strokeWidth={3} fill="url(#riskBreachFill)" activeDot={{ r: 6, fill: COLORS[4], stroke: "white", strokeWidth: 3 }}/>
          <Area isAnimationActive={false} type="monotone" dataKey="near_breach" name={l("Близко к превышению", "Near-breach")} stroke={COLORS[3]} strokeWidth={3} fill="url(#riskNearBreachFill)" activeDot={{ r: 6, fill: COLORS[3], stroke: "white", strokeWidth: 3 }}/>
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard> : null}
    {selectedUtilizationSeries ? <ChartCard
      title={l("Динамика использования лимита", "Limit utilization trend")}
      subtitle={l("Только одна и та же строка лимита по опубликованным версиям. Проценты берутся из сохранённой базы лимита источника и не усредняются между измерениями.", "Only the same limit line across published versions. Percentages use the saved source limit basis and are never averaged across dimensions.")}
      basis="source" sourceRefs={sourceRefs}
    >
      <label className="chart-control"><span>{l("Строка лимита", "Limit line")}</span><select value={selectedUtilizationSeries.key} onChange={(event) => setRiskUtilizationSeriesKey(event.target.value)}>{comparableUtilizationSeries.map((series) => <option key={series.key} value={series.key}>{series.label}</option>)}</select></label>
      <ResponsiveContainer width="100%" height={270}>
        <AreaChart data={selectedUtilizationSeries.rows} margin={{ top: 12, right: 14, left: 4, bottom: 4 }}>
          <defs><linearGradient id="riskUtilizationFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS[0]} stopOpacity={0.32}/><stop offset="100%" stopColor={COLORS[0]} stopOpacity={0.02}/></linearGradient></defs>
          <CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false}/>
          <XAxis dataKey="date" tickFormatter={(value) => shortDate(value, language)} tick={axisTick}/>
          <YAxis tickFormatter={(value) => `${compact(Number(value) * 100, language)}%`} tick={axisTick} width={52}/>
          <Tooltip content={<ChartTooltip language={language} valueKind="percent" labelKind="date"/>}/>
          <Area isAnimationActive={false} type="monotone" dataKey="utilization" name={l("Использование лимита", "Limit utilization")} stroke={COLORS[0]} strokeWidth={3} fill="url(#riskUtilizationFill)" activeDot={{ r: 6, fill: COLORS[0], stroke: "white", strokeWidth: 3 }}/>
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard> : null}
    </ChartGrid>
    {concentration.length ? <>
      <div className="risk-chart-toolbar">
        <label className="chart-control"><span>{l("Измерение", "Dimension")}</span><select value={selectedConcentrationDimension} onChange={(event) => setRiskConcentrationDimension(event.target.value)}>{concentrationDimensions.map((dimension) => <option key={dimension} value={dimension}>{concentrationDimensionLabel(dimension)}</option>)}</select></label>
        <label className="chart-control"><span>{l("Топ", "Top")}</span><select value={riskConcentrationLimit} onChange={(event) => setRiskConcentrationLimit(Number(event.target.value))}><option value={5}>5</option><option value={8}>8</option><option value={10}>10</option></select></label>
        <label className="chart-control chart-control--checkbox"><input type="checkbox" checked={riskConcentrationSharedScale} onChange={(event) => setRiskConcentrationSharedScale(event.target.checked)}/><span>{l("Общий масштаб", "Shared scale")}</span></label>
        {/* utilization is each row's actual/limit ratio - several rows
            share one identical per-issuer cap (see e.g. the "issuer"
            dimension), so this is not a share of one common whole and
            summing it across rows is meaningless. */}
        <p>{l("Использование лимита по выбранному измерению: доля собственного лимита каждой строки, а не доля портфеля. У разных строк может быть разный лимит (например, у одних эмитентов лимит меньше, у других — больше), поэтому длина столбца отражает близость к своему лимиту, а не абсолютный размер позиции.", "Limit utilization for the selected dimension: each row's share of its own limit, not a share of the portfolio. Different rows can have different limits (e.g. some issuers have a smaller cap, others a larger one), so bar length reflects closeness to that row's own limit, not the absolute size of the position.")}</p>
      </div>
      <ChartGrid single={concentration.length < 2}>
    {concentration.map(({ portfolio, top, topSourceRows, excludedCount }) => (
      <ChartCard
        key={portfolio}
        title={`${l("Использование лимита по выбранному измерению", "Limit utilization by selected dimension")} · ${portfolio}`}
        subtitle={!top.length
          ? l("Для выбранного измерения нет опубликованного использования лимита, поэтому график недоступен.", "No published limit-utilization values are available for this dimension, so the chart is unavailable.")
          : excludedCount > 0
          ? l(`${top.length} крупнейших строк по использованию лимита; ${excludedCount} строк без применимого процента исключены.`, `${top.length} largest lines by limit utilization; ${excludedCount} lines without an applicable percentage are excluded.`)
          : l(`${top.length} крупнейших строк по использованию лимита. Ранжирование отдельно для каждого портфеля.`, `${top.length} largest lines by limit utilization. Ranked independently for each portfolio.`)}
        basis="source" sourceRefs={sourceRefsFromRecords(topSourceRows, language)}
      >
        {/* Tight margins so the plot itself fills as much of the card's own
            width as possible, rather than widening the card layout - two
            cards per row is intentional; only the space inside each one
            should grow. Names are truncated (compactChartLabel) and the
            label column capped well below its old 260px ceiling so the
            column stays around a quarter of the card, not half of it. */}
        {top.length ? <ResponsiveContainer width="100%" height={Math.max(220, top.length * 48)}>
          <BarChart data={top} layout="vertical" margin={{ top: 18, right: 10, left: 4, bottom: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 5" horizontal={false}/>
            <XAxis type="number" domain={concentrationDomain} tickFormatter={(value) => `${compact(value, language)}%`} tick={axisTick}/>
            <YAxis type="category" dataKey="name" tick={axisTick} width={categoryAxisWidth(top.map((row) => row.name), 150)} interval={0} padding={{ top: 12, bottom: 12 }}/>
            <Tooltip content={<ChartTooltip language={language} valueKind="number"/>}/>
            <Bar isAnimationActive={false} dataKey="value" name={l("Использование лимита", "Limit utilization")} fill={COLORS[0]} radius={[0, 6, 6, 0]}>
              <LabelList dataKey="value" position="right" formatter={(value) => `${Number(value).toFixed(1)}%`} fill={MUTED} fontSize={11}/>
            </Bar>
          </BarChart>
        </ResponsiveContainer> : <ChartEmpty language={language}/>}
      </ChartCard>
    ))}
      </ChartGrid>
    </> : null}
    {(() => {
      // Duration (rate risk) and currency exposure (FX risk) were only
      // ever raw tables on this page, even though the Excel export
      // already charts both ("Модифицированная дюрация против лимита",
      // "Валютная экспозиция по валюте") - the two most classic risk
      // views (rate risk, FX risk) shouldn't be weaker on the website
      // than in the workbook.
      const durationRows = rows
        .filter((row) => row.dimension === "duration")
        .map((row) => {
          const modified = numeric(row.modified_duration);
          const limitValue = numeric(row.duration_limit);
          if (modified == null || limitValue == null) return null;
          const fullName = `${row.portfolio_code ?? ""} · ${row.issuer ?? row.label ?? ""}`;
          return {
            row, name: compactChartLabel(fullName, 22), fullName, modified, limit: limitValue,
            utilization: limitValue !== 0 ? modified / limitValue : 0,
          };
        })
        .filter((row): row is NonNullable<typeof row> => row != null)
        .sort((a, b) => b.utilization - a.utilization)
        .slice(0, 10);
      const exposureSourceRows = rows.filter((row) => row.dimension === "exposure_detail" && numeric(row.amount_kzt) != null);
      const exposureByCurrency = new Map<string, number>();
      for (const row of exposureSourceRows) {
        const amount = numeric(row.amount_kzt)!;
        const currency = String(row.currency ?? l("Не указано", "Not specified"));
        exposureByCurrency.set(currency, (exposureByCurrency.get(currency) ?? 0) + amount);
      }
      const exposureRows = [...exposureByCurrency.entries()]
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value);
      if (!durationRows.length && exposureRows.length < 2) return null;
      return <ChartGrid single={!durationRows.length || exposureRows.length < 2}>
        {durationRows.length ? (
          <ChartCard title={l("Контроли дюрации (топ по использованию)", "Duration controls (top by utilization)")} subtitle={l("Модифицированная дюрация против утверждённого лимита по каждой позиции; оба портфеля вместе.", "Modified duration vs. the approved limit per position; both portfolios combined.")} basis="source" sourceRefs={sourceRefsFromRecords(durationRows.map((item) => item.row), language)}>
            <ResponsiveContainer width="100%" height={Math.max(240, durationRows.length * 40)}>
              <BarChart data={durationRows} layout="vertical" margin={{ top: 18, right: 10, left: 4, bottom: 8 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 5" horizontal={false}/>
                <XAxis type="number" tick={axisTick}/>
                <YAxis type="category" dataKey="name" tick={axisTick} width={categoryAxisWidth(durationRows.map((row) => row.name), 150)} interval={0} padding={{ top: 10, bottom: 10 }}/>
                <Tooltip content={<ChartTooltip language={language} valueKind="number"/>}/>
                <Legend iconType="circle"/>
                <Bar isAnimationActive={false} dataKey="modified" name={l("Модифицированная", "Modified")} fill={COLORS[0]} radius={[0, 4, 4, 0]}/>
                <Bar isAnimationActive={false} dataKey="limit" name={l("Лимит", "Limit")} fill={COLORS[4]} radius={[0, 4, 4, 0]}/>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        ) : null}
        {exposureRows.length >= 2 ? (
          <ChartCard title={l("Валютная экспозиция по валюте", "Currency exposure by currency")} subtitle={l("Сумма из листа «Расшифровка», в KZT; детализация, не лимитная строка.", "Amounts from the exposure-detail sheet, in KZT; informational, not a limit control.")} basis="source" sourceRefs={sourceRefsFromRecords(exposureSourceRows, language)}>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={exposureRows} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} isAnimationActive={false}>
                  {exposureRows.map((row, index) => <Cell key={row.name} fill={COLORS[index % COLORS.length]} />)}
                </Pie>
                <Tooltip content={<ChartTooltip language={language} valueKind="kzt" shareOfTotal={exposureRows.reduce((sum, row) => sum + row.value, 0)}/>}/>
                <Legend iconType="circle"/>
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>
        ) : null}
      </ChartGrid>;
    })()}
  </>;
}
