import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight } from "lucide-react";
import { dashboardApi } from "../../api/client";
import type { ModuleReadResponse } from "../../api/types";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/AsyncState";
import { KpiCard } from "../../components/ui/KpiCard";
import { Panel } from "../../components/ui/Panel";
import { SourceRowLegend } from "../../components/ui/SourceRowLegend";
import { TableSearch } from "../../components/ui/TableSearch";
import { formatKzt } from "../../lib/format";
import { useI18n } from "../../i18n";
import { useScrollAnchor } from "../../hooks/useScrollAnchor";
import { displayValue, money, SourceCell, sourceLocation, type Row } from "./shared";

export function ClientDetailPanel({ recordId, onClose }: { recordId: string; onClose: () => void }) {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const query = useQuery({ queryKey: ["client-detail", recordId], queryFn: () => dashboardApi.clientDetail(recordId) });
  if (query.isLoading) return <Panel title={l("Карточка клиента", "Client detail")}><LoadingState label={l("Загрузка карточки", "Loading detail")} /></Panel>;
  if (query.error) return <Panel title={l("Карточка клиента", "Client detail")} action={<button className="button button--secondary" type="button" onClick={onClose}>{l("Закрыть", "Close")}</button>}><ErrorState error={query.error} retry={() => query.refetch()} /></Panel>;
  const data = query.data!;
  const records = data.records as Record<string, Row[]>;
  const accountRecord = (records.client_account_snapshot ?? []).find((row) => row.record_type === "client") ?? (records.client_account_snapshot ?? [])[0];
  const dashboardRecord = (records.client_dashboard_snapshot ?? [])[0];
  const profile = accountRecord ? { ...accountRecord, ...(dashboardRecord ?? {}), manager: accountRecord.manager || dashboardRecord?.manager } : dashboardRecord;
  const positions = (records.client_account_snapshot ?? []).filter((row) => row.record_type === "client_position");
  const profileFields: Array<[string, string, string]> = [
    ["client_name", "Клиент", "Client"], ["account", "Лицевой счёт", "Account"], ["iin", "ИИН", "IIN"],
    ["branch", "Филиал", "Branch"], ["manager", "Менеджер", "Manager"], ["citizenship", "Гражданство", "Citizenship"],
    ["resident", "Резидент", "Resident"], ["client_type", "Тип клиента", "Client type"], ["opening_date", "Дата открытия", "Opening date"],
    ["cash_kzt", "Деньги", "Cash"], ["total_assets_kzt", "Активы", "Assets"], ["status", "Статус", "Status"],
  ];
  return <Panel title={l("Карточка клиента", "Client detail")} subtitle={l("Полные идентификаторы показываются ответственному сотруднику локального домена; исходные строки не изменяются.", "Full identifiers are shown to the local domain operator; source rows remain unchanged.")} action={<button className="button button--secondary" type="button" onClick={onClose}>{l("Закрыть", "Close")}</button>}>
    {profile ? <>
      <dl className="governance-list">{profileFields.filter(([key]) => profile[key] != null || ["branch", "manager"].includes(key)).map(([key, ru, en]) => <div key={key}><dt>{l(ru, en)}</dt><dd>{displayValue(key, profile[key], language)}</dd></div>)}</dl>
      {accountRecord ? <p className="source-note">{l("Источник записи: ", "Record source: ")}{sourceLocation(accountRecord, language)}</p> : null}
      {positions.length ? <><h3>{l("Позиции клиента", "Client positions")}</h3><div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Эмитент", "Issuer")}</th><th>{l("Вид ЦБ", "Security type")}</th><th>{l("Код ЦБ", "Security code")}</th><th>ISIN</th><th>{l("Количество", "Quantity")}</th><th>{l("Рыночная стоимость, KZT", "Market value, KZT")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{positions.map((row, index) => <tr key={String(row.id ?? index)}><td>{displayValue("issuer", row.issuer, language)}</td><td>{displayValue("security_type", row.security_type, language)}</td><td>{displayValue("security_code", row.security_code, language)}</td><td>{displayValue("isin", row.isin, language)}</td><td>{displayValue("quantity", row.quantity, language)}</td><td>{displayValue("market_value_kzt", row.market_value_kzt, language)}</td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div></> : null}
    </> : <EmptyState title={l("Детали недоступны", "Detail unavailable")} detail={l("Опубликованная клиентская запись не содержит доступных полей.", "The published client record contains no available fields.")} />}
  </Panel>;
}

export function ClientIdentityExceptionPanel() {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const query = useQuery({ queryKey: ["client-identity-exceptions", "pending"], queryFn: () => dashboardApi.clientIdentityExceptions("pending") });
  const items = query.data?.items ?? [];
  // A per-row table here has no action to offer - there is no resolve
  // control anywhere in this app for these records, and the match itself
  // never blocks publication or hides any client data. A single count is
  // the honest representation: something to be aware of, not a queue.
  return <Panel title={l("Необязательное обогащение идентичности", "Optional identity enrichment")} subtitle={l("Сопоставление дат открытия с лицевыми счетами необязательно и не блокирует публикацию; клиентские данные уже доступны из рабочей книги независимо от результата.", "Matching opening dates to account numbers is optional and never blocks publication; client data is already available from the workbook regardless of the outcome.")}>
    {query.isLoading ? <LoadingState label={l("Загрузка списка источника", "Loading source list")} /> : query.error ? <ErrorState error={query.error} retry={() => query.refetch()} /> : items.length ? <p>{l(`${items.length} имён клиентов не сопоставлены автоматически с лицевым счётом. Действие не требуется.`, `${items.length} client names did not auto-match to an account. No action needed.`)}</p> : <EmptyState title={l("Нерешённых связей нет", "No unresolved links")} detail={l("Все доступные поля читаются непосредственно из рабочих книг.", "All available fields are read directly from the workbooks.")} />}
  </Panel>;
}

export function ClientMaturityPanel({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const [page, setPage] = useState(0);
  const pagination = useScrollAnchor<HTMLDivElement>();
  const records = ((data.records as Record<string, Row[]>).client_maturity_calendar ?? []);
  const summary = ((data.summaries as Record<string, Record<string, unknown>>).client_maturity_calendar ?? {});
  const pageSize = 20;
  const pageCount = Math.max(1, Math.ceil(records.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const visibleRows = records.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  return <Panel title={l("Календарь погашения", "Maturity calendar")} subtitle={l(`Показано ${visibleRows.length} из ${records.length} строк. События погашения и выплаты купонов из отдельного листа рабочей книги; даты не пересчитываются от текущего дня.`, `${visibleRows.length} of ${records.length} rows shown. Maturities and coupon-payment events from the workbook sheet; dates are not recalculated from today.`)} action={records.length ? <div className="table-tools"><TableSearch label={l("Поиск календаря погашения", "Search maturity calendar")} placeholder={l("Дата, клиент, инструмент", "Date, client, instrument")} /><SourceRowLegend language={language} /></div> : undefined}>
    <div className="kpi-grid kpi-grid--compact"><KpiCard label={l("События", "Events")} value={String(summary.event_count ?? records.length)} basis="source" detail={String(summary.nearest_maturity_date ?? "—")} /><KpiCard label={l("Стоимость событий", "Event value")} value={money(summary.total_value_kzt, language)} basis="source" detail={String(summary.latest_maturity_date ?? "—")} /></div>
    {records.length ? <><div className="table-scroll source-table-scroll--explicit" tabIndex={0}><table><thead><tr><th>{l("Дата", "Date")}</th><th>{l("Клиент", "Client")}</th><th>{l("Менеджер", "Manager")}</th><th>{l("Инструмент", "Instrument")}</th><th>{l("Купон", "Coupon")}</th><th>{l("Дней", "Days")}</th><th>{l("Стоимость", "Value")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{visibleRows.map((row, index) => <tr key={String(row.id ?? index)}><td>{displayValue("maturity_date", row.maturity_date, language)}</td><td>{displayValue("client_name", row.client_name, language)}</td><td>{displayValue("manager", row.manager, language)}</td><td>{displayValue("instrument", row.instrument, language)}</td><td>{displayValue("coupon_percent", row.coupon_percent, language)}</td><td>{displayValue("days_to_maturity", row.days_to_maturity, language)}</td><td>{displayValue("value_kzt", row.value_kzt, language)}</td><SourceCell row={row} language={language} /></tr>)}</tbody></table></div><div className="table-pagination" ref={pagination.ref}><span>{l(`Страница ${currentPage + 1} из ${pageCount}`, `Page ${currentPage + 1} of ${pageCount}`)}</span><label className="table-pagination__jump"><span>{l("Перейти", "Go to")}</span><select aria-label={l("Выбрать страницу", "Choose page")} value={currentPage} onChange={(event) => { pagination.anchor(); setPage(Number(event.target.value)); }}>{Array.from({ length: pageCount }, (_, index) => <option key={index} value={index}>{index + 1}</option>)}</select></label><div><button className="icon-button" type="button" aria-label={l("Предыдущая страница", "Previous page")} disabled={currentPage === 0} onClick={() => { pagination.anchor(); setPage((value) => Math.max(0, value - 1)); }}><ChevronLeft aria-hidden="true" /></button><button className="icon-button" type="button" aria-label={l("Следующая страница", "Next page")} disabled={currentPage >= pageCount - 1} onClick={() => { pagination.anchor(); setPage((value) => Math.min(pageCount - 1, value + 1)); }}><ChevronRight aria-hidden="true" /></button></div></div></> : <EmptyState title={l("Календарь не найден", "No maturity events")} detail={l("В опубликованном источнике нет строк календаря.", "The published source has no calendar rows.")} />}
  </Panel>;
}

export function ClientManagerPanel({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const records = data.records as Record<string, Row[]>;
  const rows = records.client_dashboard_snapshot ?? [];
  const summaryMix = ((data.summaries as Record<string, Record<string, unknown>>).client_dashboard_snapshot?.manager_mix ?? {}) as Record<string, Record<string, unknown>>;
  const dashboardSummary = (data.summaries as Record<string, Record<string, unknown>>).client_dashboard_snapshot ?? {};
  const accountSummary = (data.summaries as Record<string, Record<string, unknown>>).client_account_snapshot ?? {};
  const totalsDiffer = dashboardSummary.ledger_total_assets_kzt != null && accountSummary.total_assets_kzt != null && Math.abs(Number(dashboardSummary.ledger_total_assets_kzt) - Number(accountSummary.total_assets_kzt)) > 1;
  if (!rows.length && !Object.keys(summaryMix).length) return null;
  const grouped = new Map<string, { clients: number; assets: number; cash: number }>();
  for (const row of rows) {
    const manager = String(row.manager ?? "").trim() || l("Не указан", "Not supplied");
    const item = grouped.get(manager) ?? { clients: 0, assets: 0, cash: 0 };
    item.clients += 1; item.assets += Number(row.total_assets_kzt ?? 0); item.cash += Number(row.cash_kzt ?? 0); grouped.set(manager, item);
  }
  const managers = Object.keys(summaryMix).length ? Object.entries(summaryMix).map(([manager, value]) => [manager, { clients: Number(value.client_count ?? 0), assets: Number(value.total_assets_kzt ?? 0), cash: Number(value.cash_kzt ?? 0) }] as [string, { clients: number; assets: number; cash: number }]).sort((a, b) => b[1].assets - a[1].assets).slice(0, 12) : [...grouped.entries()].sort((a, b) => b[1].assets - a[1].assets).slice(0, 12);
  if (!managers.length) return null;
  return <Panel title={l("Распределение по менеджерам", "Manager distribution")} subtitle={l("Сводка рассчитана из строк клиентского реестра; суммы не смешивают валюты и отражают KZT-поля источника.", "Summary derived from client-register rows; values use the source KZT fields.")}>
    {totalsDiffer ? <div className="alert-banner alert-banner--warning"><AlertTriangle /><div><strong>{l("Сводный лист и реестр Лист4 расходятся", "Client summary and Лист4 totals differ")}</strong><p>{l("Оба значения сохранены как источник; карточки используют реестр счетов, а распределение менеджеров — лист «Клиенты».", "Both source values are retained; KPI cards use the account register while manager distribution uses the Клиенты sheet.")}</p></div></div> : null}
    <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Менеджер", "Manager")}</th><th>{l("Клиенты", "Clients")}</th><th>{l("Активы", "Assets")}</th><th>{l("Деньги", "Cash")}</th></tr></thead><tbody>{managers.map(([manager, value]) => <tr key={manager}><td><strong>{manager}</strong></td><td>{value.clients}</td><td>{formatKzt(String(value.assets), language)}</td><td>{formatKzt(String(value.cash), language)}</td></tr>)}</tbody></table></div>
  </Panel>;
}
