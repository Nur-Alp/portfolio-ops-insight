import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCheck, Database, Layers3 } from "lucide-react";
import { useMemo, useState } from "react";
import { dashboardApi } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { KpiCard } from "../components/ui/KpiCard";
import { Panel } from "../components/ui/Panel";
import { StatusPill } from "../components/ui/StatusPill";
import { formatDate } from "../lib/format";
import { useI18n } from "../i18n";
import { OperationsCharts } from "../components/charts/DomainCharts";
import { PageFrame } from "../components/ui/PageFrame";
import { ProvenanceDrawer } from "../components/ui/ProvenanceDrawer";
import { WorkQueue } from "./WorkQueue";
import { TableSearch } from "../components/ui/TableSearch";

type OperationsPayload = {
  datasets: Array<{ id: string; dataset_type: string; scope_code: string; business_date: string | null; version: number; status: string; source_filename: string; parser_version?: string | null }>;
  reconciliations: Array<{ rule_code: string; scope_code: string; business_date: string | null; difference: string | null; tolerance: string; status: string }>;
  readiness: Array<{ dataset_type: string; scope_code: string; business_date: string | null; sla_days: number; dq_blocker_count: number; dq_high_count: number; status: string }>;
};

// Maps each dataset_type back to the nav domain it's read from, purely for
// display grouping on this cross-domain register - the register itself is
// sourced from the same DatasetVersion universe every domain page reads.
const READINESS_DOMAIN_LABELS: Record<string, [string, string]> = {
  risk_limits_sobstv: ["Риск", "Risk"], risk_limits_tabys: ["Риск", "Risk"],
  fund_valuation: ["Управление активами", "Asset management"], fund_holdings: ["Управление активами", "Asset management"],
  fund_cash_liabilities: ["Управление активами", "Asset management"], fund_nav_history: ["Управление активами", "Asset management"],
  fund_prices: ["Управление активами", "Asset management"], fund_unit_series: ["Управление активами", "Asset management"],
  fund_inactive_evidence: ["Управление активами", "Asset management"],
  brokerage_trade_ledger: ["Брокеридж", "Brokerage"], derivatives_register: ["Брокеридж", "Brokerage"],
  client_account_snapshot: ["Клиенты", "Clients"], client_open_dates: ["Клиенты", "Clients"],
  client_maturity_calendar: ["Клиенты", "Clients"], client_dashboard_snapshot: ["Клиенты", "Clients"],
  corporate_finance_register: ["Корпоративные финансы", "Corporate finance"],
  accounting_landing: ["Бухгалтерия", "Accounting"], accounting_balance_sheet: ["Бухгалтерия", "Accounting"], accounting_income_statement: ["Бухгалтерия", "Accounting"],
  accounting_budget: ["Бухгалтерия", "Accounting"], accounting_portfolio_detail: ["Бухгалтерия", "Accounting"],
};

export function OperationsPage() {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const [term, setTerm] = useState("");
  const [status, setStatus] = useState("all");
  const [provenanceCode, setProvenanceCode] = useState<string | null>(null);
  const query = useQuery({ queryKey: ["operations-readiness"], queryFn: dashboardApi.operationsReadiness });
  const datasets = query.data?.datasets ?? [];
  const reconciliations = query.data?.reconciliations ?? [];
  const readiness = (query.data as unknown as OperationsPayload | undefined)?.readiness ?? [];
  const filteredDatasets = useMemo(() => {
    const normalized = term.trim().toLocaleLowerCase();
    return datasets.filter((item) => (status === "all" || item.status === status) && (!normalized || [item.dataset_type, item.scope_code, item.source_filename].some((value) => String(value ?? "").toLocaleLowerCase().includes(normalized))));
  }, [datasets, status, term]);
  const filteredReconciliations = useMemo(() => {
    const normalized = term.trim().toLocaleLowerCase();
    return reconciliations.filter((item) => !normalized || [item.rule_code, item.scope_code, item.status].some((value) => String(value ?? "").toLocaleLowerCase().includes(normalized)));
  }, [reconciliations, term]);
  if (query.isLoading) return <LoadingState label={l("Загрузка готовности источников", "Loading source readiness")} />;
  if (query.error) return <ErrorState error={query.error} retry={() => query.refetch()} />;
  const data = query.data as unknown as OperationsPayload;
  const published = datasets.filter((item) => item.status === "published").length;
  const failures = reconciliations.filter((item) => !["pass"].includes(item.status)).length;
  const scopes = new Set(datasets.map((item) => item.scope_code)).size;
  const latestDate = datasets.map((item) => item.business_date).filter(Boolean).sort().at(-1) ?? null;
  const sourceFiles = [...new Set(datasets.map((item) => item.source_filename))];
  const datasetSourceRefs = datasets.map((dataset) => ({
    workbook_name: dataset.source_filename,
    sheet_name: l("Реестр наборов (агрегат)", "Dataset registry (aggregate)"),
    row_number: null,
    parser_version: dataset.parser_version ?? "—",
    source_row_id: dataset.id,
    source_kind: "dataset" as const,
    dataset_id: dataset.id,
    dataset_type: dataset.dataset_type,
    scope_code: dataset.scope_code,
    business_date: dataset.business_date,
    version: dataset.version,
    note: l("Показатель агрегирует эту опубликованную версию набора; одной ячейки источника нет.", "This metric aggregates the published dataset version; there is no single source cell.")
  }));
  const provenanceDetails: Record<string, { label: string; value: number; explanation: string }> = {
    dataset_versions: { label: l("Версии наборов", "Dataset versions"), value: datasets.length, explanation: l("Количество зарегистрированных дочерних версий наборов данных.", "Number of registered child dataset versions.") },
    published_datasets: { label: l("Опубликовано", "Published"), value: published, explanation: l("Количество дочерних наборов со статусом «Опубликовано».", "Number of child datasets with Published status.") },
    data_scopes: { label: l("Области данных", "Data scopes"), value: scopes, explanation: l("Количество уникальных областей, присутствующих в реестре наборов.", "Number of unique data scopes present in the dataset registry.") },
    differences_date_mismatches: { label: l("Расхождения/даты", "Differences/date mismatches"), value: failures, explanation: l("Количество межсистемных сверок со статусом, отличным от pass.", "Number of cross-source reconciliations whose status is not pass.") }
  };
  const selectedDetails = provenanceCode ? provenanceDetails[provenanceCode] : null;
  const selectedProvenance = selectedDetails ? {
    code: provenanceCode!,
    label: selectedDetails.label,
    basis: "source" as const,
    value: selectedDetails.value,
    explanation: `${selectedDetails.explanation} ${sourceFiles.length ? `${l("Исходные файлы", "Source files")}: ${sourceFiles.join(", ")}.` : l("Исходные файлы не зарегистрированы.", "No source files are currently registered.")}`,
    source_refs: datasetSourceRefs
  } : null;
  return <PageFrame title={l("Операции и сверки", "Operations and reconciliations")} eyebrow="Portfolio Operations Insight / controlled sources" description={l("Рабочая очередь, независимые версии наборов и результаты межсистемных сверок.", "Work queue, independent dataset versions, and cross-source reconciliation results.")}>
    <div className="kpi-grid">
      <KpiCard label={l("Версии наборов", "Dataset versions")} value={String(datasets.length)} basis="source" detail={latestDate ? l(`Последняя дата: ${formatDate(latestDate, language)}`, `Latest date: ${formatDate(latestDate, language)}`) : undefined} icon={<Layers3 />} onBasisClick={() => setProvenanceCode("dataset_versions")} />
      <KpiCard label={l("Опубликовано", "Published")} value={String(published)} basis="source" icon={<CheckCheck />} onBasisClick={() => setProvenanceCode("published_datasets")} />
      <KpiCard label={l("Области данных", "Data scopes")} value={String(scopes)} basis="source" icon={<Database />} onBasisClick={() => setProvenanceCode("data_scopes")} />
      <KpiCard label={l("Расхождения/даты", "Differences/date mismatches")} value={String(failures)} basis="source" tone={failures ? "warning" : "positive"} icon={<AlertTriangle />} onBasisClick={() => setProvenanceCode("differences_date_mismatches")} />
    </div>
    <WorkQueue />
    <OperationsCharts datasets={data.datasets} language={language} sourceRefs={datasetSourceRefs} />
    <Panel title={l("Реестр готовности по областям", "Domain readiness register")} subtitle={l("Текущая (последняя опубликованная) версия по каждому набору, который вы загружали; SLA — начальное явное значение, а не подтверждённая политика (см. docs/todo.md).", "The current (latest published) version for every dataset_type you've uploaded; the SLA is an explicit starting default, not a confirmed policy (see docs/todo.md).")} action={<TableSearch label={l("Поиск реестра готовности", "Search readiness register")} placeholder={l("Область, набор, статус", "Domain, dataset, status")} />}>
      <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Область", "Domain")}</th><th>{l("Набор", "Dataset")}</th><th>{l("Портфель/область", "Scope")}</th><th>{l("Бизнес-дата", "Business date")}</th><th>{l("SLA, дн.", "SLA, days")}</th><th>{l("DQ блокеры", "DQ blockers")}</th><th>{l("Статус", "Status")}</th></tr></thead><tbody>{readiness.map((item) => <tr key={`${item.dataset_type}-${item.scope_code}`}><td>{READINESS_DOMAIN_LABELS[item.dataset_type]?.[language === "en" ? 1 : 0] ?? item.dataset_type}</td><td><strong>{item.dataset_type}</strong></td><td>{item.scope_code}</td><td>{item.business_date ? formatDate(item.business_date, language) : "—"}</td><td>{item.sla_days}</td><td>{item.dq_blocker_count || "—"}</td><td><StatusPill status={item.status} /></td></tr>)}</tbody></table></div>
    </Panel>
    <Panel title={l("Готовность источников", "Source readiness")} subtitle={l(`${filteredDatasets.length} из ${datasets.length} наборов показано; публикация каждого дочернего набора управляется независимо.`, `${filteredDatasets.length} of ${datasets.length} datasets shown; each child dataset is published independently.`)} action={<div className="table-tools"><label className="search-field"><span className="sr-only">{l("Поиск наборов", "Search datasets")}</span><input value={term} onChange={(event) => setTerm(event.target.value)} placeholder={l("Набор, область, файл", "Dataset, scope, file")} /></label><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label={l("Фильтр статуса", "Status filter")}><option value="all">{l("Все статусы", "All statuses")}</option><option value="published">{l("Опубликовано", "Published")}</option><option value="validated">{l("Проверено", "Validated")}</option><option value="approved">{l("Утверждено", "Approved")}</option><option value="failed">{l("Ошибка", "Failed")}</option></select></div>}>
      {datasets.length ? <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Набор", "Dataset")}</th><th>{l("Область", "Scope")}</th><th>{l("Бизнес-дата", "Business date")}</th><th>{l("Версия", "Version")}</th><th>{l("Статус", "Status")}</th><th>{l("Источник", "Source")}</th></tr></thead><tbody>{filteredDatasets.map((item) => <tr key={item.id}><td><strong>{item.dataset_type}</strong></td><td>{item.scope_code}</td><td>{formatDate(item.business_date, language)}</td><td>{item.version}</td><td><StatusPill status={item.status} /></td><td>{item.source_filename}</td></tr>)}</tbody></table></div> : <EmptyState title={l("Наборы ещё не созданы", "No datasets created yet")} detail={l("Загрузите рабочую книгу в разделе источников.", "Upload a workbook in Source uploads.")} />}
    </Panel>
    <Panel title={l("Межсистемные сверки", "Cross-source reconciliations")} subtitle={l(`${filteredReconciliations.length} из ${reconciliations.length} результатов; разные даты показываются как расхождение, а не объединяются автоматически.`, `${filteredReconciliations.length} of ${reconciliations.length} results; different dates are shown as a mismatch and are not merged automatically.`)}>
      {reconciliations.length ? <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Правило", "Rule")}</th><th>{l("Область", "Scope")}</th><th>{l("Дата", "Date")}</th><th>{l("Разница", "Difference")}</th><th>{l("Допуск", "Tolerance")}</th><th>{l("Статус", "Status")}</th></tr></thead><tbody>{filteredReconciliations.map((item, index) => <tr key={`${item.rule_code}-${index}`}><td><strong>{item.rule_code}</strong></td><td>{item.scope_code}</td><td>{formatDate(item.business_date, language)}</td><td>{item.difference ?? "—"}</td><td>{item.tolerance}</td><td><StatusPill status={item.status} /></td></tr>)}</tbody></table></div> : <EmptyState title={l("Сверки пока недоступны", "No reconciliations yet")} detail={l("Они появятся после публикации участвующих источников на сопоставимые даты.", "They appear after participating sources are published for comparable dates.")} />}
    </Panel>
    <ProvenanceDrawer metric={selectedProvenance} onClose={() => setProvenanceCode(null)} />
  </PageFrame>;
}
