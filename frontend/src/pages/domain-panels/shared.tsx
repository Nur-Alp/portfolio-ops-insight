import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { dashboardApi } from "../../api/client";
import type { ActionItem, DatasetVersion, ModuleReadResponse } from "../../api/types";
import type { components } from "../../api/schema";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/AsyncState";
import { Drawer } from "../../components/ui/Drawer";
import { Panel } from "../../components/ui/Panel";
import { StatusPill } from "../../components/ui/StatusPill";
import { formatDate, formatKzt, formatNumber, formatPercent, humanize } from "../../lib/format";
import { useI18n } from "../../i18n";
import type { ChartDomain } from "../../components/charts/DomainCharts";

// Types, generic helpers, and small dispatchers used by more than one
// domain panel file. Anything genuinely specific to a single domain lives in
// that domain's own file instead (see FundPanels.tsx, TreasuryPanels.tsx,
// BrokeragePanels.tsx, ClientsPanels.tsx, AccountingPanels.tsx, RiskPanels.tsx).

export type DomainKind = ChartDomain;
export type Row = Record<string, unknown>;
export type Provenance = components["schemas"]["MetricProvenance"];
export const STANDARD_TABLE_PAGE_SIZE = 20;

export function card(label: string, value: string, basis: "source" | "derived" | "unavailable", detail = "", metricCode?: string, recordIds?: string[], metricFields?: string[], tone?: "neutral" | "positive" | "warning" | "danger") { return { label, value, basis, detail, metricCode, recordIds, metricFields, tone }; }

export function money(value: unknown, language: "ru" | "en") { return value == null ? "—" : formatKzt(String(value), language); }
// The accounting balance sheet / income statement / budget workbooks state
// every *_kzt figure in thousands of tenge (source header: "в тысячах
// тенге" / "в тыс тг") - unlike accounting_portfolio_detail, whose
// carrying_value_kzt the source states directly "в тенге" (full units).
// Scale up so every KZT figure on this page is the same real-world unit;
// the raw source tables/exports still show the untouched thousands values,
// since those mirror the source cell exactly.
export function moneyThousands(value: unknown, language: "ru" | "en") { return value == null ? "—" : formatKzt(Number(value) * 1000, language); }
export function displayValue(key: string, value: unknown, language: "ru" | "en") { if (value == null || value === "") return ["branch", "manager"].includes(key) ? (language === "en" ? "Not supplied" : "Не указано") : "—"; if (["cash_kzt", "total_assets_kzt", "securities_value_kzt", "fee_received_kzt", "purchase_value_kzt", "value_kzt", "limit_kzt", "actual_kzt", "free_limit_kzt", "amount_kzt", "carrying_value_kzt", "current_period_kzt", "prior_period_kzt", "quarter_kzt", "ytd_kzt", "prior_quarter_kzt", "prior_ytd_kzt", "market_value_kzt", "accrued_income_kzt", "year_2023_kzt", "year_2024_kzt", "budget_9m_2025_kzt", "actual_9m_2025_kzt", "budget_2025_kzt", "oct_2025_kzt", "nov_2025_kzt", "dec_2025_kzt", "forecast_2025_kzt", "deviation_kzt"].includes(key)) return formatKzt(String(value), language); if (["limit_usd", "actual_usd", "free_limit_usd"].includes(key)) return `${formatNumber(String(value), language, 2)} $`; if (["limit_pct", "actual_pct", "weight_pct", "coupon_pct", "execution_pct", "commission_rate"].includes(key)) return formatPercent(Number(value) * 100, 1, language); if (["amount", "quantity", "days_to_maturity", "coupon_percent", "coupon_rate", "cash_share", "income", "duration_limit", "modified_duration", "duration_headroom", "fx_rate", "amount_native", "carrying_value_native", "purchase_price"].includes(key)) return formatNumber(String(value), language); if (["date", "trade_date", "maturity_date", "coupon_payment_date", "purchase_date", "settlement_date", "opening_date"].includes(key)) return formatDate(String(value), language); return Array.isArray(value) ? value.join(", ") : String(value); }
export function sourceLocation(row: Row, language: "ru" | "en") {
  const source = row.source;
  if (!source || typeof source !== "object" || Array.isArray(source)) return language === "en" ? "Unavailable" : "Недоступно";
  const value = source as Record<string, unknown>;
  const filename = String(value.filename ?? value.workbook_name ?? "");
  const sheet = String(value.sheet_name ?? "");
  const rowNumber = value.row_number == null ? "" : String(value.row_number);
  const cell = value.source_cell ? `${language === "en" ? "cell" : "ячейка"} ${String(value.source_cell)}` : "";
  const column = value.source_column_letter ? `${language === "en" ? "column" : "столбец"} ${String(value.source_column_letter)}` : "";
  const location = [sheet, rowNumber ? `${language === "en" ? "row" : "строка"} ${rowNumber}` : "", cell, column].filter(Boolean).join(" · ");
  return [filename, location].filter(Boolean).join(" · ") || (language === "en" ? "Unavailable" : "Недоступно");
}

// Every table's source cell is now a compact provenance marker. The row-level
// click handler above reads these data attributes and opens the existing
// source-preview drawer without rendering a long workbook/cell URL in every
// row. Rows without an exact source cell remain non-clickable.
export function SourceCell({ row, language }: { row: Row; language: "ru" | "en" }) {
  const source = row.source;
  const rowId = row.id;
  if (!source || typeof source !== "object" || Array.isArray(source) || typeof rowId !== "string") {
    return <td className="source-cell source-cell--empty" aria-hidden="true" />;
  }
  const value = source as Record<string, unknown>;
  const sourceCell = value.source_cell;
  const sheetName = value.sheet_name;
  if (typeof sourceCell !== "string" || typeof sheetName !== "string") {
    return <td className="source-cell source-cell--empty" aria-hidden="true" />;
  }
  return <td
    className="source-cell"
    aria-hidden="true"
    title={language === "en" ? "Click the row to preview the source cell" : "Нажмите на строку, чтобы просмотреть исходную ячейку"}
    data-source-row-id={rowId}
    data-source-cell={sourceCell}
    data-source-sheet-name={sheetName}
    data-source-workbook-name={String(value.filename ?? value.workbook_name ?? "")}
  ></td>;
}

export function hasExactSourceCell(row: Row): boolean {
  const source = row.source;
  return Boolean(
    typeof row.id === "string" &&
    source && typeof source === "object" && !Array.isArray(source) &&
    typeof (source as Record<string, unknown>).source_cell === "string" &&
    typeof (source as Record<string, unknown>).sheet_name === "string"
  );
}

export function isRepoTrade(row: Row): boolean {
  if (row.is_repo === true) return true;
  return ["security_type", "instrument", "instrument_type", "trade_type", "deal_type", "transaction_type", "counterparty"].some((key) => {
    const text = String(row[key] ?? "").trim().toLocaleLowerCase();
    return text.includes("репо") || /\brepo\b/.test(text);
  });
}

export function DomainSourceMeta({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const dates = data.report_dates.filter(Boolean);
  const versions = [...new Set(data.sources.map((source) => source.version).filter(Boolean))];
  if (!dates.length && !versions.length) return null;
  return <div className="domain-source-meta"><span>{l("Источник", "Source")}: {data.sources.length}</span>{dates.length ? <span>{l("даты", "dates")}: {dates.map((date) => formatDate(date, language)).join(" · ")}</span> : null}{versions.length ? <span>{l("версии", "versions")}: {versions.join(", ")}</span> : null}</div>;
}

export function DomainTable({ kind, rows, language, onClientDetail }: { kind: DomainKind; rows: Row[]; language: "ru" | "en"; onClientDetail?: (recordId: string) => void }) {
  const definitions: Record<DomainKind, Array<[string, string, string]>> = {
    "asset-management": [["instrument", "Инструмент", "Instrument"], ["isin", "ISIN", "ISIN"], ["quantity", "Количество", "Quantity"], ["currency", "Валюта", "Currency"], ["purchase_date", "Дата покупки", "Purchase date"], ["maturity_date", "Дата погашения", "Maturity date"], ["coupon_rate", "Купон, %", "Coupon, %"], ["purchase_value_kzt", "Покупная стоимость", "Purchase value"]],
    treasury: [],
    brokerage: [["trade_date", "Дата сделки", "Trade date"], ["side", "Сторона", "Side"], ["client_name", "Клиент", "Client"], ["venue", "Площадка", "Venue"], ["isin", "ISIN", "ISIN"], ["amount", "Сумма", "Amount"], ["currency", "Валюта", "Currency"], ["execution_status", "Исполнение", "Execution"]],
    clients: [["client_name", "Клиент", "Client"], ["account", "Лицевой счёт", "Account"], ["iin", "ИИН", "IIN"], ["branch", "Филиал", "Branch"], ["manager", "Менеджер", "Manager"], ["cash_kzt", "Деньги", "Cash"], ["total_assets_kzt", "Активы", "Assets"]],
    "corporate-finance": [["issuer", "Эмитент", "Issuer"], ["subject", "Предмет", "Mandate"], ["isins", "ISIN", "ISINs"], ["placement_raw", "Объём", "Placement"], ["demand_raw", "Спрос", "Demand"], ["investors", "Инвесторы", "Investors"], ["commission_rate", "Ставка комиссии", "Commission rate"], ["fee_received_kzt", "Вознаграждение", "Fee received"], ["duration_raw", "Срок", "Duration"]],
    accounting: [["line_code", "Код строки", "Line code"], ["line_label", "Наименование статьи", "Line label"], ["section", "Раздел", "Section"], ["current_period_kzt", "На конец периода, тыс. KZT", "Current period, thousand KZT"], ["prior_period_kzt", "На начало периода, тыс. KZT", "Prior period, thousand KZT"]],
    risk: [["portfolio_code", "Портфель", "Portfolio"], ["dimension", "Измерение", "Dimension"], ["label", "Наименование", "Name"], ["limit_pct", "Лимит, %", "Limit, %"], ["actual_pct", "Факт, %", "Actual, %"], ["limit_kzt", "Лимит, KZT", "Limit, KZT"], ["actual_kzt", "Факт, KZT", "Actual, KZT"], ["free_limit_kzt", "Свободный лимит, KZT", "Free limit, KZT"], ["limit_usd", "Лимит, USD", "Limit, USD"], ["actual_usd", "Факт, USD", "Actual, USD"], ["free_limit_usd", "Свободный лимит, USD", "Free limit, USD"], ["signal", "Сигнал", "Signal"]]
  };
  const columns = definitions[kind];
  return <div className="table-scroll domain-table" tabIndex={0}><table><thead><tr>{columns.map(([key, ru, en]) => <th key={key}>{language === "en" ? en : ru}</th>)}<th className="source-column-header">{language === "en" ? "Source" : "Источник"}</th>{onClientDetail ? <th>{language === "en" ? "Detail" : "Карточка"}</th> : null}</tr></thead><tbody>{rows.map((row, index) => {
    const sourceBacked = hasExactSourceCell(row);
    return <tr key={String(row.id ?? index)} data-source-row={sourceBacked || undefined} tabIndex={sourceBacked ? 0 : undefined} aria-label={sourceBacked ? (language === "en" ? "Open source preview" : "Открыть просмотр источника") : undefined}>{columns.map(([key]) => <td key={key}>{key === "signal" && row[key] ? <StatusPill status={String(row[key])} /> : displayValue(key, row[key], language)}</td>)}<SourceCell row={row} language={language} />{onClientDetail ? <td><button className="button button--secondary" type="button" onClick={() => onClientDetail(String(row.id))}>{language === "en" ? "Open" : "Открыть"}</button></td> : null}</tr>;
  })}</tbody></table></div>;
}

export function ReadinessChecklist({ rows }: { rows: Array<Record<string, unknown>> }) {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  return <Panel title={l("Контракт готовности источника", "Source-readiness contract")} subtitle={l("Показатели не включаются, пока входы не получены и не утверждены.", "Metrics remain disabled until inputs are received and approved.")}><div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Требование", "Requirement")}</th><th>{l("Статус", "Status")}</th><th>{l("Комментарий", "Comment")}</th></tr></thead><tbody>{rows.map((row, index) => <tr key={index}><td><strong>{String(row.requirement ?? "—")}</strong></td><td><StatusPill status={String(row.status ?? "expected")} /></td><td>{String(row.detail ?? "—")}</td></tr>)}</tbody></table></div></Panel>;
}

export function FormulaAuditNotice({ data, language }: { data: ModuleReadResponse; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const summaries = data.summaries as Record<string, Record<string, unknown>>;
  const audits = Object.entries(summaries)
    .map(([datasetType, summary]) => ({ datasetType, audit: summary.formula_audit as Record<string, unknown> | undefined, consumed: summary.consumed_formula_audit as Record<string, unknown> | undefined }))
    .filter((item): item is { datasetType: string; audit: Record<string, unknown>; consumed: Record<string, unknown> | undefined } => Boolean(item.audit));
  const positiveCount = (value: unknown) => typeof value === "number" ? value > 0 : value != null && value !== "" && Number(value) > 0;
  const isActionable = ({ audit, consumed }: { audit: Record<string, unknown>; consumed: Record<string, unknown> | undefined }) => {
    const status = String(audit.formula_status ?? "unknown");
    const format = String(audit.format ?? "").toLowerCase();
    const gateStatus = consumed?.status;
    // BIFF/.xls formula records can be counted, but the reader cannot expose
    // their cached results. This is an expected limitation, not a defect and
    // must not turn every legacy workbook into an orange warning.
    const legacyInspectionLimit = format === "xls" && status === "formula_records_detected" && consumed?.status === "not_inspectable";
    if (legacyInspectionLimit) return false;
    // Workbook-wide audits also see unused helper cells and literal error
    // values. If the parser checked every formula-backed published field and
    // the gate passed, those unrelated cells are evidence, not a dashboard
    // publication error.
    if (gateStatus === "passed") return false;
    return consumed?.status === "blocked"
      || status === "formula_errors"
      || status === "source_errors"
      || status === "blank_cached_results"
      || positiveCount(audit.formula_error_count)
      || positiveCount(audit.error_value_count)
      || positiveCount(audit.blank_cached_formula_count)
      || !["ok", "no_formulas", "formula_records_detected"].includes(status);
  };
  const needsReview = audits.filter(isActionable);
  if (!needsReview.length) return null;
  const hasPublicationBlocker = needsReview.some(({ consumed }) => consumed?.status === "blocked");
  const details = needsReview.map(({ datasetType, audit, consumed }) => {
    const status = String(audit.formula_status ?? "unknown");
    const format = String(audit.format ?? "");
    const errors = audit.formula_error_count == null ? "—" : String(audit.formula_error_count);
    const sourceErrors = audit.error_value_count == null ? "—" : String(audit.error_value_count);
    const blanks = audit.blank_cached_formula_count == null ? "—" : String(audit.blank_cached_formula_count);
    const gate = String(consumed?.status ?? "not_available");
    const checked = String(consumed?.checked_formula_cells ?? 0);
    return `${datasetType}: ${status}${format ? ` (${format})` : ""}; ${l("ошибок формул", "formula errors")} ${errors}; ${l("ошибок значений", "source errors")} ${sourceErrors}; ${l("пустых кэшей", "blank caches")} ${blanks}; ${l("проверка опубликованных полей", "published-field gate")} ${gate} (${checked})`;
  }).join(" · ");
  const explanation = hasPublicationBlocker
    ? l("Проверка опубликованных полей блокирует публикацию .xlsx, если используемый результат формулы пуст или ошибочен.", "The published-field gate blocks an .xlsx publication when a consumed formula result is blank or erroneous.")
    : l("Обнаружена проблема в содержимом источника, но проверка опубликованных полей не блокирует публикацию. Исправьте исходную книгу и загрузите новую версию, если это значение используется.", "A source-content issue was detected, but the published-field gate is not blocking publication. Correct the source workbook and upload a new version if this value is used.");
  return <div className="alert-banner alert-banner--warning"><AlertTriangle /><div><strong>{l("Проверка источника требует внимания", "Source check requires attention")}</strong><p>{details}. {explanation} {l("Приложение не пересчитывает произвольные формулы; для .xls результаты формул недоступны этому читателю.", "The application does not recalculate arbitrary formulas; .xls formula results are not exposed by this reader.")}</p></div></div>;
}

export function ActionItemsPanel({ domain, language }: { domain: "risk" | "accounting"; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<"open" | "resolved">("open");
  const [selected, setSelected] = useState<ActionItem | null>(null);
  const [ownerId, setOwnerId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [assignReason, setAssignReason] = useState("");
  const [resolveComment, setResolveComment] = useState("");
  const [reopenReason, setReopenReason] = useState("");
  const [actionError, setActionError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newKind, setNewKind] = useState("");
  const [newTitle, setNewTitle] = useState("");

  const items = useQuery({ queryKey: ["action-items", domain, statusFilter], queryFn: () => dashboardApi.actionItems(domain, statusFilter) });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["action-items", domain] });

  const create = useMutation({
    mutationFn: () => dashboardApi.createActionItem({ domain, kind: newKind.trim(), title: newTitle.trim() }),
    onSuccess: async () => { setActionError(""); setNewKind(""); setNewTitle(""); setShowCreate(false); await invalidate(); },
    onError: (error: Error) => setActionError(error.message)
  });
  const assign = useMutation({
    mutationFn: (variables: { ownerId: string | null; dueDate: string | null; reason: string }) => dashboardApi.assignActionItem(selected!.id, variables),
    onSuccess: async (updated) => { setActionError(""); setAssignReason(""); await invalidate(); setSelected((current) => current ? { ...current, ...updated } : current); },
    onError: (error: Error) => setActionError(error.message)
  });
  const resolve = useMutation({
    mutationFn: () => dashboardApi.resolveActionItem(selected!.id, resolveComment),
    onSuccess: async (updated) => { setActionError(""); setResolveComment(""); await invalidate(); setSelected((current) => current ? { ...current, ...updated } : current); },
    onError: (error: Error) => setActionError(error.message)
  });
  const reopen = useMutation({
    mutationFn: () => dashboardApi.reopenActionItem(selected!.id, reopenReason),
    onSuccess: async (updated) => { setActionError(""); setReopenReason(""); await invalidate(); setSelected((current) => current ? { ...current, ...updated } : current); },
    onError: (error: Error) => setActionError(error.message)
  });

  const openItem = (item: ActionItem) => {
    setSelected(item);
    setOwnerId(item.owner_id ?? "");
    setDueDate(item.due_date ?? "");
    setAssignReason("");
    setResolveComment("");
    setReopenReason("");
    setActionError("");
  };

  const rows = items.data?.items ?? [];

  return <Panel
    title={l("Пункты действий", "Action items")}
    subtitle={l("Операционные задачи по превышениям и шагам закрытия периода; отдельно от замечаний качества данных.", "Operational to-dos for breach exceptions and close steps; separate from data-quality findings.")}
    action={<div className="table-tools">
      <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "open" | "resolved")} aria-label={l("Статус", "Status")}>
        <option value="open">{l("Открытые", "Open")}</option>
        <option value="resolved">{l("Закрытые", "Resolved")}</option>
      </select>
      <button className="button button--secondary" type="button" onClick={() => setShowCreate((value) => !value)}>{l("Новый пункт", "New item")}</button>
    </div>}
  >
    {showCreate ? <div className="assignment-form">
      <label>{l("Тип", "Kind")}<input value={newKind} onChange={(event) => setNewKind(event.target.value)} placeholder={domain === "risk" ? l("например, breach_exception", "e.g. breach_exception") : l("например, close_step", "e.g. close_step")} maxLength={60} /></label>
      <label>{l("Заголовок", "Title")}<textarea value={newTitle} onChange={(event) => setNewTitle(event.target.value)} maxLength={500} /></label>
      {actionError ? <div className="inline-error" role="alert">{actionError}</div> : null}
      <button className="button button--primary" type="button" disabled={create.isPending || !newKind.trim() || !newTitle.trim()} onClick={() => create.mutate()}>{create.isPending ? l("Сохранение…", "Saving…") : l("Создать", "Create")}</button>
    </div> : null}
    {items.isLoading
      ? <LoadingState label={l("Загрузка пунктов действий", "Loading action items")} />
      : items.error
        ? <ErrorState error={items.error} retry={() => items.refetch()} />
        : rows.length
          ? <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Заголовок", "Title")}</th><th>{l("Тип", "Kind")}</th><th>{l("Ответственный", "Owner")}</th><th>{l("Статус", "Status")}</th></tr></thead><tbody>{rows.map((item) => <tr key={item.id} tabIndex={0} onClick={() => openItem(item)} onKeyDown={(event) => { if (event.key === "Enter") openItem(item); }}><td><strong>{item.title}</strong></td><td>{humanize(item.kind, language)}</td><td>{item.owner_id ? <span>{item.owner_id}{item.due_date ? ` · ${formatDate(item.due_date, language)}` : ""}{item.is_overdue ? <> · <StatusPill status="overdue" /></> : null}</span> : <span className="unavailable-note unavailable-note--pill">{l("Не назначено", "Unassigned")}</span>}</td><td><StatusPill status={item.status} /></td></tr>)}</tbody></table></div>
          : <EmptyState title={statusFilter === "open" ? l("Нет открытых пунктов", "No open items") : l("Нет закрытых пунктов", "No resolved items")} detail={l("Создайте пункт для отслеживания исключения или шага закрытия.", "Create an item to track an exception or close step.")} />}
    <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.title ?? l("Пункт действия", "Action item")} subtitle={selected ? humanize(selected.kind, language) : undefined}>
      {selected ? <div className="drawer-stack">
        <div className="drawer-section">
          <h3>{l("Статус", "Status")}</h3>
          <p><StatusPill status={selected.status} /> {selected.owner_id ? l(`Назначено: ${selected.owner_id}`, `Assigned to ${selected.owner_id}`) : l("Не назначено", "Unassigned")}{selected.due_date ? ` · ${formatDate(selected.due_date, language)}` : ""}{selected.is_overdue ? <> · <StatusPill status="overdue" /></> : null}</p>
          {selected.assignment_reason ? <p className="unavailable-note">{selected.assignment_reason}</p> : null}
        </div>
        {actionError ? <div className="inline-error" role="alert">{actionError}</div> : null}
        {selected.status === "open" ? <>
          <div className="drawer-section">
            <h3>{l("Назначить ответственного", "Assign owner")}</h3>
            <div className="assignment-form">
              <label>{l("Ответственный", "Owner")}<input value={ownerId} onChange={(event) => setOwnerId(event.target.value)} maxLength={200} /></label>
              <label>{l("Срок", "Due date")}<input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} disabled={!ownerId.trim()} /></label>
              <label>{l("Обоснование", "Reason")}<textarea value={assignReason} onChange={(event) => setAssignReason(event.target.value)} maxLength={4000} /></label>
              <button className="button button--primary" type="button" disabled={assign.isPending || !assignReason.trim()} onClick={() => assign.mutate({ ownerId: ownerId.trim() || null, dueDate: ownerId.trim() ? (dueDate || null) : null, reason: assignReason })}>{assign.isPending ? l("Сохранение…", "Saving…") : l("Назначить", "Assign")}</button>
            </div>
          </div>
          <div className="drawer-section">
            <h3>{l("Закрыть пункт", "Resolve")}</h3>
            <div className="assignment-form">
              <label>{l("Комментарий закрытия", "Resolution comment")}<textarea value={resolveComment} onChange={(event) => setResolveComment(event.target.value)} maxLength={4000} /></label>
              <button className="button button--primary" type="button" disabled={resolve.isPending || !resolveComment.trim()} onClick={() => resolve.mutate()}>{resolve.isPending ? l("Сохранение…", "Saving…") : l("Закрыть", "Resolve")}</button>
            </div>
          </div>
        </> : <div className="drawer-section">
          <h3>{l("Переоткрыть", "Reopen")}</h3>
          <p>{selected.resolved_by ? l(`Закрыл: ${selected.resolved_by}`, `Resolved by ${selected.resolved_by}`) : null}{selected.resolution_comment ? ` — ${selected.resolution_comment}` : ""}</p>
          <div className="assignment-form">
            <label>{l("Причина повторного открытия", "Reopen reason")}<textarea value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} maxLength={4000} /></label>
            <button className="button button--secondary" type="button" disabled={reopen.isPending || !reopenReason.trim()} onClick={() => reopen.mutate()}>{reopen.isPending ? l("Сохранение…", "Saving…") : l("Переоткрыть", "Reopen")}</button>
          </div>
        </div>}
      </div> : null}
    </Drawer>
  </Panel>;
}

// A version's own report date is the most useful way to tell versions apart,
// but not every dataset type carries one (some accounting landing uploads
// have no explicitly labelled report date in the source). Fall through to
// the next most specific real date rather than showing "Недоступно"
// whenever any date actually exists; the upload date is labelled distinctly
// since it answers a different question (when it was uploaded, not what
// period it reports on) and must not be presented as if it were one.
export function versionOptionLabel(item: DatasetVersion, language: "ru" | "en"): string {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const date = item.business_date
    ? formatDate(item.business_date, language)
    : item.source_report_date
      ? formatDate(item.source_report_date, language)
      : l(`загрузка ${formatDate(item.created_at.slice(0, 10), language)}`, `uploaded ${formatDate(item.created_at.slice(0, 10), language)}`);
  const status = item.status === "superseded" ? ` · ${l("заменена", "superseded")}` : "";
  // DQ blocker/high findings are exactly the kind of thing that should stop
  // someone from silently pinning an unsafe historical version - surfaced
  // here rather than only after they've already switched to it.
  const dqCount = item.dq_blocker_count + item.dq_high_count;
  const dqWarning = dqCount ? ` · ⚠ DQ ${dqCount}` : "";
  return `${date} · ${l(`Версия ${item.version}`, `Version ${item.version}`)}${status}${dqWarning}`;
}

export function VersionPicker({ source, selectedSourceUploadId, onSelect, language }: { source: ModuleReadResponse["sources"][number]; selectedSourceUploadId: string | null; onSelect: (sourceUploadId: string | null) => void; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const query = useQuery({
    queryKey: ["dataset-versions", source.dataset_type, source.scope_code],
    queryFn: () => dashboardApi.datasetVersions(source.dataset_type, source.scope_code)
  });
  // Only offer versions that ever held real, viewable data - a withdrawn,
  // rejected, or failed row was never a coherent published state, so
  // "viewing" it would just show a blank/garbage dataset.
  const options = (query.data?.items ?? []).filter((item) => item.status === "published" || item.status === "superseded");
  return <select aria-label={l("Версия рабочей книги", "Workbook version")} value={selectedSourceUploadId ?? "latest"} disabled={query.isLoading} onChange={(event) => onSelect(event.target.value === "latest" ? null : event.target.value)}>
    <option value="latest">{l("Текущая (последняя)", "Current (latest)")}</option>
    {options.flatMap((item) => item.source_upload_id ? [<option key={item.id} value={item.source_upload_id} title={item.source_filename}>{versionOptionLabel(item, language)}</option>] : [])}
  </select>;
}

// The four accounting statement types come from four independently-uploaded
// physical workbooks (docs/phase-2-groundwork-risk-accounting.md), all under
// the single "ACCOUNTING" scope - unlike risk's SOBSTV/TABYS split, so each
// picker is keyed and labelled by dataset_type rather than scope_code. Kept
// here (rather than in AccountingPanels.tsx) because DatasetVersionPicker
// below - shared with risk's picker bar - needs the same label lookup.
export const ACCOUNTING_DATASET_TYPE_LABELS: Record<string, [string, string]> = {
  accounting_balance_sheet: ["Баланс", "Balance sheet"],
  accounting_income_statement: ["Прибыли и убытки", "Income statement"],
  accounting_budget: ["Бюджет", "Budget"],
  accounting_portfolio_detail: ["Детализация портфеля", "Portfolio detail"],
};

export function DatasetVersionPicker({ source, selectedDatasetId, onSelect, language }: { source: ModuleReadResponse["sources"][number]; selectedDatasetId: string | null; onSelect: (datasetId: string | null) => void; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const query = useQuery({ queryKey: ["dataset-versions", source.dataset_type, source.scope_code], queryFn: () => dashboardApi.datasetVersions(source.dataset_type, source.scope_code) });
  const options = (query.data?.items ?? []).filter((item) => item.status === "published" || item.status === "superseded");
  const accountingLabel = ACCOUNTING_DATASET_TYPE_LABELS[source.dataset_type];
  const groupLabel = accountingLabel ? (language === "en" ? accountingLabel[1] : accountingLabel[0]) : source.scope_code;
  return <select aria-label={`${groupLabel} ${l("Версия рабочей книги", "Workbook version")}`} value={selectedDatasetId ?? "latest"} disabled={query.isLoading} onChange={(event) => onSelect(event.target.value === "latest" ? null : event.target.value)}>
    <option value="latest">{l("Текущая (последняя)", "Current (latest)")}</option>
    {options.map((item) => <option key={item.id} value={item.id} title={item.source_filename}>{versionOptionLabel(item, language)}</option>)}
  </select>;
}

export function domainCardProvenance(card: { label: string; value: string; basis: "source" | "derived" | "unavailable"; detail?: string; metricCode?: string; recordIds?: string[]; metricFields?: string[] }, refs: Provenance["source_refs"], language: "ru" | "en"): Provenance {
  // A card whose value is computed from a specific subset of records (e.g.
  // "Breaches" from only the breached rows) must only show evidence for
  // that subset - otherwise every card shows the same unfiltered list of
  // every record regardless of what was actually clicked. Dataset-level
  // refs (workbook/version identity) stay regardless, since they're
  // relevant background for any card, not row-specific evidence.
  const scoped = card.recordIds
    ? (refs ?? []).filter((ref) => ref.source_kind !== "row" || (ref.source_row_id != null && card.recordIds!.includes(ref.source_row_id)))
    : refs;
  // Beyond scoping to the right records, retarget each row's evidence at the
  // specific payload field that explains the card's number (e.g. the amount
  // that breached, or the duration that exceeded its limit) instead of
  // always the record's classification label - the label answers "which
  // row" but not "why", which is the more useful question for these cards.
  const retargeted = card.metricFields
    ? (scoped ?? []).map((ref) => retargetRefToField(ref, card.metricFields!, language))
    : scoped;
  // A card backed by hundreds or thousands of rows (e.g. brokerage turnover
  // across an entire trade ledger) must not dump one line per row into the
  // drawer - that buries the handful of rows a reviewer actually wants to
  // spot-check under a wall of identical-looking entries. Collapse each
  // (workbook, sheet) group above the threshold into one summary line plus
  // a small clickable sample.
  const scopedRefs = aggregateRowRefs(retargeted, language);
  return {
    code: `domain_${card.label}`,
    label: card.label,
    basis: card.basis,
    value: card.value === "—" ? null : card.value,
    explanation: language === "en" ? `${card.detail ? `${card.detail}. ` : ""}The source manifest identifies the exact workbook and published dataset version; row/cell evidence is available in the related table.` : `${card.detail ? `${card.detail}. ` : ""}Реестр источников указывает точную рабочую книгу и опубликованную версию набора; строка/ячейка доступна в связанной таблице.`,
    source_refs: scopedRefs,
  };
}

const EVIDENCE_GROUP_THRESHOLD = 12;
const EVIDENCE_SAMPLE_SIZE = 6;

export function aggregateRowRefs(refs: Provenance["source_refs"], language: "ru" | "en"): Provenance["source_refs"] {
  const list = refs ?? [];
  const rowRefs = list.filter((ref) => ref.source_kind === "row");
  if (rowRefs.length <= EVIDENCE_GROUP_THRESHOLD) return list;
  const otherRefs = list.filter((ref) => ref.source_kind !== "row");
  const groups = new Map<string, typeof rowRefs>();
  for (const ref of rowRefs) {
    const key = `${ref.workbook_name}|${ref.sheet_name}`;
    const bucket = groups.get(key);
    if (bucket) bucket.push(ref); else groups.set(key, [ref]);
  }
  const out = [...otherRefs];
  for (const group of groups.values()) {
    if (group.length <= EVIDENCE_GROUP_THRESHOLD) { out.push(...group); continue; }
    const columns = group.map((ref) => ref.source_column).filter((value): value is number => typeof value === "number");
    const minColumn = columns.length ? Math.min(...columns) : null;
    const maxColumn = columns.length ? Math.max(...columns) : null;
    const columnRange = minColumn == null || maxColumn == null ? null : minColumn === maxColumn ? excelColumnLetter(minColumn) : `${excelColumnLetter(minColumn)}-${excelColumnLetter(maxColumn)}`;
    const count = group.length.toLocaleString(language === "en" ? "en-US" : "ru-RU");
    const sample = group.slice(0, EVIDENCE_SAMPLE_SIZE);
    const summaryRef: NonNullable<Provenance["source_refs"]>[number] & { remaining_rows: typeof group } = {
      workbook_name: group[0].workbook_name,
      sheet_name: group[0].sheet_name,
      row_number: null,
      parser_version: group[0].parser_version,
      source_row_id: `aggregate:${group[0].workbook_name}:${group[0].sheet_name}`,
      source_cell: null,
      source_column: null,
      source_column_letter: null,
      source_header: null,
      source_kind: "workbook",
      field: language === "en" ? `${count} rows${columnRange ? `, columns ${columnRange}` : ""}` : `строк: ${count}${columnRange ? `, столбцы ${columnRange}` : ""}`,
      note: language === "en"
        ? "Too many rows to list individually - this metric is backed by every one of them. A representative sample is shown below; expand to see every row."
        : "Слишком много строк для полного списка - показатель опирается на все из них. Ниже показана репрезентативная выборка; разверните, чтобы увидеть все строки.",
      // Non-schema field: the rows beyond the visible sample, so the
      // ProvenanceDrawer can expand this summary into the full list on
      // demand instead of it being a dead end.
      remaining_rows: group.slice(EVIDENCE_SAMPLE_SIZE),
    };
    out.push(summaryRef);
    out.push(...sample);
  }
  return out;
}

export function excelColumnLetter(column: number): string {
  let value = column;
  let letters = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    letters = String.fromCharCode(65 + remainder) + letters;
    value = Math.floor((value - 1) / 26);
  }
  return letters;
}

export const DOMAIN_FIELD_LABELS: Record<string, [string, string]> = {
  actual_kzt: ["фактическая сумма (KZT)", "actual amount (KZT)"],
  actual_usd: ["фактическая сумма (USD)", "actual amount (USD)"],
  modified_duration: ["модифицированная дюрация", "modified duration"],
  nav_kzt: ["СЧА (KZT)", "NAV (KZT)"],
  unit_value_kzt: ["стоимость пая (KZT)", "unit value (KZT)"],
  securities_value_kzt: ["стоимость ценных бумаг (KZT)", "securities value (KZT)"],
  amount: ["сумма сделки", "trade amount"],
  client_name: ["имя клиента", "client name"],
  account: ["номер счёта", "account number"],
  total_assets_kzt: ["суммарные активы (KZT)", "total assets (KZT)"],
  cash_kzt: ["денежные средства (KZT)", "cash (KZT)"],
  duration_raw: ["срок сделки", "deal duration"],
};

export function retargetRefToField<T extends { field_columns?: Record<string, { source_cell?: string; source_column?: number; source_column_letter?: string }>; source_cell?: string | null; source_column?: number | null; source_column_letter?: string | null; field?: string | null }>(ref: T, preferredFields: string[], language: "ru" | "en"): T {
  const fieldColumns = ref.field_columns;
  if (!fieldColumns) return ref;
  const matchedField = preferredFields.find((field) => fieldColumns[field] != null);
  if (!matchedField) return ref;
  const target = fieldColumns[matchedField];
  const label = DOMAIN_FIELD_LABELS[matchedField];
  return {
    ...ref,
    source_cell: target.source_cell ?? ref.source_cell,
    source_column: target.source_column ?? ref.source_column,
    source_column_letter: target.source_column_letter ?? ref.source_column_letter,
    field: label ? (language === "en" ? label[1] : label[0]) : ref.field,
  };
}

export function domainSourceRefs(data: ModuleReadResponse, language: "ru" | "en"): Provenance["source_refs"] {
  const datasetRefs = data.sources.map((source) => ({
    workbook_name: source.source_filename,
    sheet_name: language === "en" ? "Dataset registry (aggregate)" : "Реестр наборов (агрегат)",
    row_number: null,
    // ProvenanceReference.parser_version is required and non-nullable, but
    // ModuleSourceManifest's own field is optional/nullable - fall back to
    // an explicit unavailable marker rather than passing null through.
    parser_version: source.parser_version ?? "—",
    source_row_id: source.dataset_id,
    source_cell: null,
    source_kind: "dataset" as const,
    // Dataset-level evidence has no single source cell. Keep the upload id
    // on the runtime reference so the evidence card can open/download the
    // immutable original workbook instead.
    source_upload_id: source.source_upload_id,
    dataset_id: source.dataset_id,
    dataset_type: source.dataset_type,
    scope_code: source.scope_code,
    business_date: source.business_date,
    version: source.version,
    note: language === "en" ? "This KPI aggregates the published dataset; use the related table for row/cell-level evidence." : "Этот показатель агрегирует опубликованный набор; точная строка/ячейка доступна в связанной таблице."
  }));
  const recordRefs = Object.values(data.records).flatMap((records) => records.flatMap((record) => {
    const source = record.source;
    if (!source || typeof source !== "object") return [];
    const sourceValue = source as Record<string, unknown>;
    const rowNumber = Number(sourceValue.row_number ?? sourceValue.row);
    if (!Number.isFinite(rowNumber)) return [];
    const filename = String(sourceValue.filename ?? sourceValue.workbook_name ?? "").trim();
    const sheet = String(sourceValue.sheet_name ?? sourceValue.sheet ?? "").trim();
    if (!filename || !sheet) return [];
    return [{
      workbook_name: filename,
      sheet_name: sheet,
      row_number: rowNumber,
      parser_version: String(sourceValue.parser_version ?? "—"),
      source_row_id: String(record.id ?? `${sheet}:${rowNumber}`),
      source_column: typeof sourceValue.source_column === "number" ? sourceValue.source_column : null,
      source_column_letter: typeof sourceValue.source_column_letter === "string" ? sourceValue.source_column_letter : null,
      source_cell: typeof sourceValue.source_cell === "string" ? sourceValue.source_cell : null,
      source_header: typeof sourceValue.source_header === "string" ? sourceValue.source_header : null,
      // Every current parser that records a column/cell anchors it on the
      // record's own classification label (see ingestion/multi_source.py) -
      // naming that plainly here is honest; the generic "row" fallback the
      // drawer otherwise uses would imply no specific field was identified.
      field: typeof sourceValue.source_cell === "string" ? (language === "en" ? "label" : "наименование") : undefined,
      source_kind: "row" as const,
      note: language === "en" ? "Exact source row for a published domain record." : "Точная строка источника опубликованной записи домена.",
      // Not part of the ProvenanceReference schema - carried through at
      // runtime only so domainCardProvenance can retarget a card's evidence
      // at the specific payload field it actually summarizes (e.g. the
      // amount that breached) instead of always the classification label.
      field_columns: sourceValue.field_columns && typeof sourceValue.field_columns === "object" ? sourceValue.field_columns as Record<string, { source_cell?: string; source_column?: number; source_column_letter?: string }> : undefined
    }];
  }));
  const seen = new Set<string>();
  return [...datasetRefs, ...recordRefs].filter((ref) => {
    const key = [ref.workbook_name, ref.sheet_name, ref.row_number, ref.source_cell, ref.source_row_id].join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
