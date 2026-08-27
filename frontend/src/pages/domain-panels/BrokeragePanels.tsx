import type { ModuleReadResponse } from "../../api/types";
import { Panel } from "../../components/ui/Panel";
import { EmptyState } from "../../components/ui/AsyncState";
import { SourceRowLegend } from "../../components/ui/SourceRowLegend";
import { TableSearch } from "../../components/ui/TableSearch";
import { displayValue, isRepoTrade, SourceCell, type Row } from "./shared";

export function BrokerageRepoToggle({ data, includeRepo, onChange, language }: { data: ModuleReadResponse; includeRepo: boolean; onChange: (value: boolean) => void; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const rows = ((data.records as Record<string, Row[]>).brokerage_trade_ledger ?? []);
  const repoCount = rows.filter(isRepoTrade).length;
  return <Panel title={l("Фильтр РЕПО", "Repo filter")} subtitle={l("Оборот, количество сделок и графики пересчитываются по строкам источника.", "Turnover, trade counts, and charts are recalculated from source rows.")}>
    <label className="toggle-control"><input type="checkbox" checked={includeRepo} onChange={(event) => onChange(event.target.checked)} disabled={repoCount === 0} /><span>{l("Включать сделки РЕПО", "Include repo deals")}</span><small>{repoCount ? l(`Найдено сделок РЕПО: ${repoCount}`, `Repo trades detected: ${repoCount}`) : l("В опубликованном источнике явных сделок РЕПО не найдено", "No explicit repo trades were detected in the published source")}</small></label>
  </Panel>;
}

export function BrokerageDerivativesPanel({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const records = (data.records as Record<string, Row[]>).derivatives_register ?? [];
  return <Panel title={l("Реестр производных инструментов", "Derivatives register")} subtitle={l("Производные инструменты показываются отдельной таблицей; сроки и статусы не смешиваются со сделками.", "Derivatives are shown separately; maturities and statuses are not mixed with trades.")} action={<div className="table-tools"><TableSearch label={l("Поиск производных инструментов", "Search derivatives")} placeholder={l("Инструмент, статус, дата", "Instrument, status, date")} /><SourceRowLegend language={language} /></div>}>
    {records.length ? <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Тип инструмента", "Instrument type")}</th><th>{l("Идентификатор", "Identifier")}</th><th>{l("Рынок", "Market")}</th><th>{l("Базовый актив / рейтинг", "Underlying / rating")}</th><th>{l("Контрагент", "Counterparty")}</th><th>{l("Количество", "Quantity")}</th><th>{l("Сумма", "Amount")}</th><th>{l("Валюта", "Currency")}</th><th>{l("Дата расчёта", "Settlement date")}</th><th>{l("Статус обязательства", "Obligation status")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{records.map((row, index) => <tr key={String(row.id ?? index)}><td><strong>{displayValue("instrument_type", row.instrument_type ?? row.instrument, language)}</strong></td><td>{displayValue("identifier", row.identifier, language)}</td><td>{displayValue("market", row.market, language)}</td><td>{displayValue("underlying", row.underlying, language)}</td><td>{displayValue("counterparty", row.counterparty, language)}</td><td>{displayValue("quantity", row.quantity, language)}</td><td>{displayValue("amount", row.amount, language)}</td><td>{displayValue("currency", row.currency, language)}</td><td>{displayValue("settlement_date", row.settlement_date ?? row.maturity_date, language)}</td><td>{displayValue("obligation_status", row.obligation_status, language)}</td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div> : <EmptyState title={l("Производные не найдены", "No derivatives found")} detail={l("Источник не содержит зарегистрированных производных инструментов.", "The source contains no registered derivatives.")} />}
  </Panel>;
}
