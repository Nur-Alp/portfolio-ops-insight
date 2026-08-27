import { useQuery } from "@tanstack/react-query";
import { AlertOctagon, AlertTriangle, Eye, Upload } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { dashboardApi } from "../api/client";
import type { DatasetVersion } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { KpiCard } from "../components/ui/KpiCard";
import { Panel } from "../components/ui/Panel";
import { StatusPill } from "../components/ui/StatusPill";
import { formatDate } from "../lib/format";
import { useI18n } from "../i18n";
import { TableSearch } from "../components/ui/TableSearch";

function domainLabel(dataset: DatasetVersion, language: "ru" | "en") {
  const labels: Record<string, [string, string]> = {
    portfolio_snapshot: ["Бэк офис / OSIP", "Back office / OSIP"],
    fund_valuation: ["Бэк офис / оценка фонда", "Back office / fund valuation"],
    fund_holdings: ["Бэк офис / позиции фонда", "Back office / fund holdings"],
    fund_cash_liabilities: ["Бэк офис / деньги и обязательства", "Back office / cash and liabilities"],
    fund_nav_history: ["Бэк офис / история NAV", "Back office / NAV history"],
    fund_prices: ["Бэк офис / цены", "Back office / prices"],
    fund_unit_series: ["Бэк офис / стоимость пая", "Back office / unit history"],
    client_account_snapshot: ["Клиентский / счета и позиции", "Client operations / accounts and holdings"],
    brokerage_trade_ledger: ["Клиентский / сделки", "Client operations / trades"],
    derivatives_register: ["Клиентский / производные", "Client operations / derivatives"],
    client_open_dates: ["Клиентский / даты открытия", "Client operations / opening dates"],
    corporate_finance_register: ["Корпфин / реестр", "Corporate finance / register"],
    accounting_landing: ["Бухгалтерия / landing", "Accounting / landing"],
  };
  return labels[dataset.dataset_type]?.[language === "en" ? 1 : 0] ?? dataset.dataset_type;
}

export function WorkQueue() {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const query = useQuery({ queryKey: ["dataset-versions"], queryFn: () => dashboardApi.datasetVersions() });
  if (query.isLoading) return <LoadingState label={l("Загрузка моей очереди", "Loading my work queue")} />;
  if (query.error) return <ErrorState error={query.error} retry={() => query.refetch()} />;

  const datasets = query.data?.items ?? [];
  const awaitingReview = datasets.filter((item) => item.status === "validated");
  const readyToPublish = datasets.filter((item) => item.status === "approved");
  // Source-first datasets are already readable. Their DQ findings stay
  // visible on the source and domain pages, but do not create a review task.
  const dqBlockers = datasets.filter((item) => item.status !== "published" && item.issues.some((issue) => ["blocker", "high"].includes(issue.severity) && !issue.acknowledged_by));
  const actionItems = [...awaitingReview, ...readyToPublish, ...dqBlockers.filter((item) => !awaitingReview.includes(item) && !readyToPublish.includes(item))];
  const stale = datasets.filter((item) => ["stale", "aging", "future"].includes(item.freshness));
  const failed = datasets.filter((item) => item.status === "failed");

  return <>
    <div className="kpi-grid">
      <KpiCard label={l("Ожидают проверки", "Awaiting review")} value={String(awaitingReview.length)} basis="source" tone={awaitingReview.length ? "warning" : "positive"} icon={<Eye />} />
      <KpiCard label={l("Готовы к публикации", "Ready to publish")} value={String(readyToPublish.length)} basis="source" tone={readyToPublish.length ? "warning" : "positive"} icon={<Upload />} />
      <KpiCard label={l("Блокеры DQ", "DQ blockers")} value={String(dqBlockers.length)} basis="source" tone={dqBlockers.length ? "warning" : "positive"} icon={<AlertOctagon />} />
    </div>

    <Panel title={l("Рабочая очередь", "Work queue")} subtitle={l("Для локальных источников просмотр доступен сразу; действия ниже нужны только для незавершённых или контролируемых версий.", "Local source-first data is readable immediately; the actions below are only for incomplete or controlled versions.")} action={<TableSearch label={l("Поиск рабочей очереди", "Search work queue")} placeholder={l("Набор, область, файл", "Dataset, scope, file")} />}>
      {actionItems.length ? <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Набор", "Dataset")}</th><th>{l("Область", "Scope")}</th><th>{l("Дата", "Date")}</th><th>{l("Статус", "Status")}</th><th>DQ</th><th>{l("Действие", "Action")}</th></tr></thead><tbody>{actionItems.map((item) => <tr key={item.id}><td><strong>{domainLabel(item, language)}</strong><small>{item.source_filename}</small></td><td>{item.scope_code}</td><td>{formatDate(item.business_date, language)}</td><td><StatusPill status={item.status} /></td><td>{item.issues.filter((issue) => ["blocker", "high"].includes(issue.severity)).length}</td><td><Link className="button button--secondary" to={taskRoute(item.dataset_type) as never}>{item.status === "validated" ? l("Проверить", "Review") : item.status === "approved" ? l("Опубликовать", "Publish") : l("Открыть", "Open")}</Link></td></tr>)}</tbody></table></div> : <EmptyState title={l("Очередь пуста", "Queue is clear")} detail={l("Новых действий для вашей рабочей области нет.", "There are no new actions for your work area.")} />}
    </Panel>

    <Panel title={l("Предупреждения источников", "Source warnings")} subtitle={l("Свежесть и нерешённые замечания требуют внимания владельца домена.", "Freshness and unresolved findings require domain-owner attention.")}>
      {stale.length ? <div className="alert-banner alert-banner--warning"><AlertTriangle /><div><strong>{l(`${stale.length} набор(ов) требуют проверки свежести`, `${stale.length} dataset(s) need freshness review`)}</strong><p>{stale.slice(0, 8).map((item) => `${domainLabel(item, language)} · ${item.freshness}`).join("; ")}</p></div></div> : <EmptyState title={l("Просроченных источников нет", "No stale sources")} detail={l("Опубликованные наборы находятся в пределах текущего окна свежести.", "Published datasets are within the current freshness window.")} />}
    </Panel>

    <Panel title={l("Уведомления", "Notifications")} subtitle={l("Системные события по вашей рабочей области.", "System events for your assigned workspaces.")} action={<TableSearch label={l("Поиск уведомлений", "Search notifications")} placeholder={l("Тип, набор, действие", "Type, dataset, action")} />}>
      {failed.length || dqBlockers.length ? <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Тип", "Type")}</th><th>{l("Набор", "Dataset")}</th><th>{l("Следующее действие", "Next action")}</th></tr></thead><tbody>{failed.map((item) => <tr key={`failed-${item.id}`}><td><StatusPill status="failed" /></td><td>{domainLabel(item, language)}</td><td>{l("Проверить ошибку разбора и повторить загрузку", "Inspect parser failure and re-upload")}</td></tr>)}{dqBlockers.map((item) => <tr key={`dq-${item.id}`}><td><StatusPill status="high" /></td><td>{domainLabel(item, language)}</td><td>{l("Проверить замечание и решить, нужна ли корректировка источника", "Review the finding and decide whether the source needs correction")}</td></tr>)}</tbody></table></div> : <EmptyState title={l("Новых уведомлений нет", "No new notifications")} detail={l("Очередь и источники не требуют немедленного внимания.", "The queue and sources need no immediate attention.")} />}
    </Panel>

  </>;
}

function taskRoute(datasetType: string): string {
  if (datasetType.startsWith("fund_")) return "/asset-management";
  if (datasetType === "portfolio_snapshot") return "/";
  if (datasetType === "client_account_snapshot" || datasetType === "client_open_dates" || datasetType === "client_maturity_calendar" || datasetType === "client_dashboard_snapshot") return "/clients";
  if (datasetType === "brokerage_trade_ledger" || datasetType === "derivatives_register") return "/brokerage";
  if (datasetType === "corporate_finance_register") return "/corporate-finance";
  if (datasetType === "accounting_landing") return "/accounting";
  return "/operations";
}
