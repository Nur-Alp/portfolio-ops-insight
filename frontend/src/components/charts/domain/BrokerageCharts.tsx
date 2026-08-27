import { BarChart, Bar, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ModuleReadResponse } from "../../../api/types";
import {
  ChartCard, ChartEmpty, ChartGrid, ChartTooltip, Donut, COLORS, GRID, axisTick, collapseOthers, compact, countField,
  countFieldFallback, executionVenueColor, isBuy, isRepoTrade, isSell, numeric, objectValues, sourceRefsFromRecords,
  stockBondColor, sumSecurityClassKzt, type Language, type MetricProvenance, type ProvenanceRef, type Row,
} from "./shared";

export function BrokerageCharts({ data, language, sourceRefs = [], includeRepo = true }: { data: ModuleReadResponse; language: Language; sourceRefs?: ProvenanceRef[]; includeRepo?: boolean }) {
  const records = data.records as Record<string, Row[]>;
  const summaries = data.summaries as Record<string, Record<string, unknown>>;
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const trades = (records.brokerage_trade_ledger ?? []).filter((row) => includeRepo || !isRepoTrade(row));
  const currencies = [...new Set(trades.map((row) => String(row.currency ?? "Не указано").trim() || "Не указано"))].sort();
  const turnover = currencies.map((currency) => {
    const rows = trades.filter((row) => String(row.currency ?? "Не указано").trim() === currency);
    const buy = rows.filter((row) => isBuy(row.side)).reduce((sum, row) => sum + Math.abs(numeric(row.amount) ?? 0), 0);
    const sell = rows.filter((row) => isSell(row.side)).reduce((sum, row) => sum + Math.abs(numeric(row.amount) ?? 0), 0);
    // Logarithmic axes cannot represent zero. Keep zero in the source data,
    // but omit it from the plotted series rather than fabricating a value.
    // Recharts' own `scale="log"` on <YAxis> mis-computes <Bar> heights
    // (each bar's baseline collapses toward the axis floor instead of the
    // log-transformed value) - confirmed visually against this same data
    // exported to Excel, where the equivalent chart renders correctly.
    // Pre-transforming to log10 on a linear axis sidesteps the bug; the
    // real value stays in `buy`/`sell` for the tooltip (see ChartTooltip).
    return {
      currency, buy: buy > 0 ? buy : null, sell: sell > 0 ? sell : null,
      buyLog: buy > 0 ? Math.log10(buy) : null, sellLog: sell > 0 ? Math.log10(sell) : null,
    };
  });
  const tradeCounts = currencies
    .map((currency) => ({ name: currency, value: trades.filter((row) => String(row.currency ?? "Не указано").trim() === currency).length }))
    .filter((item) => item.value > 0)
    .map((item) => ({ ...item, valueLog: Math.log10(item.value) }));
  const venues = collapseOthers(
    objectValues(countField(trades, "venue")),
    l("Прочие", "Other"),
    5,
    (name) => /неорганизован|unorgan/i.test(name),
  );
  const instrumentMix = collapseOthers(
    objectValues(countFieldFallback(trades, ["security_type", "instrument_type"])),
    l("Прочие", "Other"),
    8,
  );
  const fxRatesKzt = (summaries.brokerage_trade_ledger?.fx_rates_kzt ?? {}) as Record<string, string>;
  const fxRateDate = summaries.brokerage_trade_ledger?.fx_rate_date as string | undefined;
  const stockBondMix = sumSecurityClassKzt(trades, fxRatesKzt, l);
  const brokerageTradeRefs = sourceRefsFromRecords(trades, language);
  const stockBondCurrenciesMissingRate = [...new Set(
    trades.map((row) => String(row.currency ?? "").trim()).filter((currency) => currency && fxRatesKzt[currency] === undefined),
  )];
  const stockBondProvenance: MetricProvenance = {
    code: "brokerage_stock_bond_turnover_kzt",
    label: l("Акции против облигаций", "Stocks vs bonds"),
    basis: "derived",
    value: null,
    formula: l(
      "Σ |Сумма сделки| × курс KZT из опубликованного набора по каждой строке. Акции: «акции», ADR и GDR; облигации: «облигац», «ГЦБ» и «евронот». ETF и индексные инструменты не включаются ни в одну группу.",
      "Σ |trade amount| × the published dataset's KZT rate for each trade row. Equities: shares, ADRs and GDRs; bonds: bonds, government securities and Eurobonds. ETFs and index instruments are not included in either group.",
    ),
    explanation: l(
      `${includeRepo ? "РЕПО включены" : "РЕПО исключены"}. Курс применён на дату ${fxRateDate ?? "набора данных"}; строки без курса исключены из KZT-итога, а не заменены нулём.`,
      `Repo is ${includeRepo ? "included" : "excluded"}. The rate is applied as of ${fxRateDate ?? "the dataset business date"}; rows without a rate are excluded from the KZT total rather than replaced with zero.`,
    ),
    source_refs: brokerageTradeRefs,
    inputs: [{
      code: "brokerage_trade_rows",
      label: l("Строки реестра сделок", "Trade-ledger rows"),
      basis: "source",
      value: String(trades.length),
      source_refs: brokerageTradeRefs,
    }],
  };
  return <ChartGrid>
    <ChartCard title={l("Оборот покупок и продаж", "Buy and sell turnover")} subtitle={l(`${includeRepo ? "РЕПО включены" : "РЕПО исключены"}; суммы указаны в валюте каждой сделки, не являются эквивалентом KZT. Логарифмическая шкала показывает разные порядки величины.`, `${includeRepo ? "Repo included" : "Repo excluded"}; amounts are shown in each trade currency, not as KZT equivalents. The logarithmic scale keeps different orders of magnitude visible.`)} basis="source" sourceRefs={sourceRefs}>
      {turnover.length ? <ResponsiveContainer width="100%" height={270}><BarChart data={turnover} margin={{ top: 18, right: 14, left: 4, bottom: 4 }}><CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false}/><XAxis dataKey="currency" tick={axisTick}/><YAxis domain={[0, "auto"]} allowDataOverflow tickFormatter={(value) => compact(10 ** Number(value), language)} tick={axisTick} width={68}/><Tooltip content={<ChartTooltip language={language} valueKind="number" currencyField="currency"/>}/><Legend iconType="circle"/><Bar isAnimationActive={false} dataKey="buyLog" name={l("Покупки", "Buys")} fill={COLORS[2]} radius={[6, 6, 0, 0]}/><Bar isAnimationActive={false} dataKey="sellLog" name={l("Продажи", "Sells")} fill={COLORS[4]} radius={[6, 6, 0, 0]}/></BarChart></ResponsiveContainer> : <ChartEmpty language={language}/>}
    </ChartCard>
    <ChartCard title={l("Количество сделок", "Trade count")} subtitle={l(`${includeRepo ? "РЕПО включены" : "РЕПО исключены"}; логарифмическая шкала делает малые валютные группы видимыми.`, `${includeRepo ? "Repo included" : "Repo excluded"}; a logarithmic scale keeps small currency groups visible.`)} basis="source" sourceRefs={sourceRefs}>
      {tradeCounts.length ? <ResponsiveContainer width="100%" height={270}><BarChart data={tradeCounts} margin={{ top: 18, right: 14, left: 4, bottom: 4 }}><CartesianGrid stroke={GRID} strokeDasharray="3 5" vertical={false}/><XAxis dataKey="name" tick={axisTick}/><YAxis domain={[0, "auto"]} allowDataOverflow allowDecimals={false} tickFormatter={(value) => compact(10 ** Number(value), language)} tick={axisTick} width={42}/><Tooltip content={<ChartTooltip language={language} valueKind="number"/>}/><Bar isAnimationActive={false} dataKey="valueLog" name={l("Сделки", "Trades")} fill={COLORS[1]} radius={[6, 6, 0, 0]}/></BarChart></ResponsiveContainer> : <ChartEmpty language={language}/>}
    </ChartCard>
    {venues.length > 1 ? <ChartCard compact title={l("Площадки исполнения", "Execution venues")} subtitle={l("Количество сделок по площадкам; малые площадки объединены в «Прочие», а неорганизованный рынок сохранён отдельно.", "Trade count by execution venue; smaller venues are grouped into “Other”, while the unorganised market remains separate.")} basis="source" sourceRefs={sourceRefs}><Donut data={venues} language={language} valueKind="number" height={220} minAngle={3} colorFor={executionVenueColor}/></ChartCard> : null}
    {instrumentMix.length > 1 ? <ChartCard compact title={l("Состав по типам инструментов", "Instrument type mix")} subtitle={l("Количество сделок по виду ценной бумаги; малые категории объединены в «Прочие».", "Trade count by security type; smaller categories are grouped into “Other”.")} basis="source" sourceRefs={sourceRefs}><Donut data={instrumentMix} language={language} valueKind="number" height={250} minAngle={3}/></ChartCard> : null}
    {stockBondMix.length > 1 ? <ChartCard compact title={l("Акции против облигаций", "Stocks vs bonds")} subtitle={l(
      `Оборот в KZT по виду ценной бумаги (акции/депозитарные расписки против облигаций/ГЦБ); фонды и индексные инструменты не отнесены ни к тому, ни к другому. Курс НБК на ${fxRateDate ?? "дату набора данных"}.${stockBondCurrenciesMissingRate.length ? ` Курс недоступен для: ${stockBondCurrenciesMissingRate.join(", ")} - эти сделки исключены из суммы.` : ""}`,
      `KZT turnover by security type (equities/depositary receipts vs. bonds/government securities); funds and index instruments aren't forced into either bucket. NBK rate as of ${fxRateDate ?? "the dataset's business date"}.${stockBondCurrenciesMissingRate.length ? ` No rate available for: ${stockBondCurrenciesMissingRate.join(", ")} - those trades are excluded from the total.` : ""}`,
    )} basis="derived" sourceRefs={brokerageTradeRefs} provenance={stockBondProvenance}><Donut data={stockBondMix} language={language} valueKind="kzt" height={220} minAngle={3} colorFor={stockBondColor}/></ChartCard> : null}
  </ChartGrid>;
}
