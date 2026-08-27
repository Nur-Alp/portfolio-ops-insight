import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertOctagon, CheckCheck, Download, Search, ShieldAlert, UserCog } from "lucide-react";
import { useMemo, useState } from "react";
import type { DataQualityIssue, DatasetVersion } from "../api/types";
import { dashboardApi } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { BasisBadge } from "../components/ui/BasisBadge";
import { Drawer } from "../components/ui/Drawer";
import { KpiCard } from "../components/ui/KpiCard";
import { Panel } from "../components/ui/Panel";
import { StatusPill } from "../components/ui/StatusPill";
import { useSelectedSnapshot } from "../hooks/useSelectedSnapshot";
import { formatDate, formatMetricLabel, formatMetricReason, humanize } from "../lib/format";
import { useI18n } from "../i18n";
import { PageFrame } from "../components/ui/PageFrame";
import { useProvenance } from "../components/ui/ProvenanceContext";
import type { SourceReferenceWithUpload } from "../components/ui/SourcePreviewDrawer";

const severities = ["all", "blocker", "high", "medium", "low"];

export function DataQualityPage() {
  const { language, t } = useI18n();
  const { openSourcePreview } = useProvenance();
  const selectedSnapshot = useSelectedSnapshot();
  const { search, portfolios, snapshotId } = selectedSnapshot;
  const osipEnabled = selectedSnapshot.osipEnabled ?? Boolean(snapshotId);
  const queryClient = useQueryClient();
  const [severity, setSeverity] = useState("all");
  const [term, setTerm] = useState("");
  const [selected, setSelected] = useState<DataQualityIssue | null>(null);
  const [ownerId, setOwnerId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [assignReason, setAssignReason] = useState("");
  const [assignError, setAssignError] = useState("");
  const issues = useQuery({ queryKey: ["issues", snapshotId, language], queryFn: () => dashboardApi.issues(snapshotId), enabled: Boolean(snapshotId) });
  const metrics = useQuery({ queryKey: ["metric-definitions"], queryFn: dashboardApi.metrics, enabled: osipEnabled });
  const genericDatasets = useQuery({ queryKey: ["dataset-versions"], queryFn: () => dashboardApi.datasetVersions() });
  const assign = useMutation({
    mutationFn: (variables: { ownerId: string | null; dueDate: string | null; reason: string }) =>
      dashboardApi.assignDqIssue(selected!.id, variables),
    onSuccess: async (updated) => {
      setAssignError("");
      setAssignReason("");
      await queryClient.invalidateQueries({ queryKey: ["issues", snapshotId] });
      setSelected((current) => (current ? { ...current, ...updated } : current));
    },
    onError: (error: Error) => setAssignError(error.message)
  });
  const exportIssues = useMutation({
    mutationFn: () => dashboardApi.exportDqIssues(snapshotId, { term, severity: severity as "all" | "blocker" | "high" | "medium" | "low" })
  });
  const filtered = useMemo(() => {
    const normalized = term.trim().toLocaleLowerCase();
    return (issues.data?.items ?? []).filter((issue) =>
      (severity === "all" || issue.severity === severity) &&
      (!normalized || [issue.code, issue.message, ...issue.affected_fields].some((value) => value.toLocaleLowerCase().includes(normalized)))
    );
  }, [issues.data, severity, term]);
  if ((osipEnabled && (portfolios.isLoading || issues.isLoading || metrics.isLoading)) || genericDatasets.isLoading) return <LoadingState label={t("dq.loading")} />;
  const error = genericDatasets.error ?? (osipEnabled ? portfolios.error ?? issues.error ?? metrics.error : null);
  if (error) return <ErrorState error={error} />;
  if (!osipEnabled || !snapshotId) {
    const datasets = genericDatasets.data?.items ?? [];
    return <PageFrame title={t("dq.title")} eyebrow="Portfolio Operations Insight / Controls" description={language === "en" ? "Workbook exceptions across independently controlled sources." : "Замечания рабочих книг по независимо контролируемым источникам."}>
      <GenericDatasetIssues datasets={datasets} term={term} severity={severity} language={language} />
      {datasets.length ? <div className="unavailable-note">{t("dq.noOsipSelected")}</div> : <EmptyState title={osipEnabled ? t("holding.noPublished") : t("dq.noDomainDatasets")} detail={osipEnabled ? t("dq.noPublishedDetail", { portfolio: search.portfolio }) : t("dq.noDomainDatasetsDetail")} />}
    </PageFrame>;
  }
  if (!issues.data || !metrics.data) return null;
  const counts = issues.data.items.reduce<Record<string, number>>((result, issue) => ({ ...result, [issue.severity]: (result[issue.severity] ?? 0) + 1 }), {});
  const uniqueCodes = new Set(issues.data.items.map((issue) => issue.code)).size;
  const acknowledged = issues.data.items.filter((issue) => issue.acknowledgement).length;
  const disabledMetrics = metrics.data.items.filter((metric) => !metric.enabled);
  const criticalIssues = issues.data.items.filter((issue) => ["blocker", "high"].includes(issue.severity));
  const unacknowledgedCritical = criticalIssues.filter((issue) => !issue.acknowledgement);

  const openIssue = (issue: DataQualityIssue) => {
    setSelected(issue);
    setOwnerId(issue.owner_id ?? "");
    setDueDate(issue.due_date ?? "");
    setAssignReason("");
    setAssignError("");
  };

  return (
    <PageFrame title={t("dq.title")} eyebrow={t("dq.eyebrow")} description={t("dq.description")}>
      <div className="kpi-grid">
        <KpiCard label={t("dq.findings")} value={String(issues.data.items.length)} basis="source" detail={t("dq.rules", { count: uniqueCodes })} icon={<ShieldAlert />} />
        <KpiCard label={t("dq.critical")} value={String((counts.blocker ?? 0) + (counts.high ?? 0))} basis="source" tone="danger" icon={<AlertOctagon />} />
        <KpiCard label={t("dq.acknowledged")} value={String(acknowledged)} basis="source" tone="positive" icon={<CheckCheck />} />
        <KpiCard label={t("dq.disabledMetrics")} value={String(disabledMetrics.length)} basis="unavailable" tone="warning" />
      </div>
      {unacknowledgedCritical.length ? <div className="alert-banner alert-banner--danger"><AlertOctagon aria-hidden="true" /><div><strong>{t("dq.blocked")}</strong><p>{t("dq.blockedDetail", { codes: unacknowledgedCritical.map((issue) => issue.code).join(", ") })}</p></div></div> : <div className="alert-banner alert-banner--success"><CheckCheck aria-hidden="true" /><div><strong>{t("dq.allAcknowledged")}</strong><p>{t("dq.allAcknowledgedDetail")}</p></div></div>}
      <div className="content-grid content-grid--two-thirds">
        <Panel title={t("dq.panel")} subtitle={t("dq.filtered", { count: filtered.length })} action={<div className="table-tools"><label className="search-field"><Search aria-hidden="true" /><span className="sr-only">{t("dq.searchLabel")}</span><input value={term} onChange={(event) => setTerm(event.target.value)} placeholder={t("dq.search")} /></label><select value={severity} onChange={(event) => setSeverity(event.target.value)} aria-label={t("dq.severityFilter")}>{severities.map((value) => <option key={value} value={value}>{value === "all" ? t("dq.allSeverities") : humanize(value, language)}</option>)}</select><button className="button button--secondary table-tools__export" type="button" disabled={exportIssues.isPending} onClick={() => exportIssues.mutate()}><Download aria-hidden="true" /> {exportIssues.isPending ? t("common.prepare") : t("common.exportExcel")}</button></div>}>
          {exportIssues.error ? <div className="inline-error" role="alert">{exportIssues.error.message}</div> : null}
          <div className="table-scroll" tabIndex={0}><table className="clickable-table"><thead><tr><th>{t("dq.rule")}</th><th>{t("dq.severity")}</th><th>{t("dq.finding")}</th><th>{t("dq.affected")}</th><th>{t("dq.sourceEvidenceCount")}</th><th>{t("dq.owner")}</th><th>{t("dq.review")}</th></tr></thead><tbody>{filtered.map((issue) => <tr key={issue.id} tabIndex={0} onClick={() => openIssue(issue)} onKeyDown={(event) => { if (event.key === "Enter") openIssue(issue); }}><td><strong>{issue.code}</strong></td><td><StatusPill status={issue.severity} /></td><td>{issue.message}</td><td>{issue.affected_fields.slice(0, 2).map((field) => humanize(field, language)).join(", ")}{issue.affected_fields.length > 2 ? ` +${issue.affected_fields.length - 2}` : ""}</td><td>{issue.source_refs.length ? t("cash.sourceRows", { count: issue.source_refs.length }) : t("dq.portfolio")}</td><td>{issue.owner_id ? <span>{issue.owner_id}{issue.due_date ? ` · ${t("dq.byDate", { date: formatDate(issue.due_date, language) })}` : ""}{issue.is_overdue ? <StatusPill status="overdue" /> : null}</span> : <span className="unavailable-note">{t("dq.unassigned")}</span>}</td><td>{issue.acknowledgement ? <StatusPill status="approved" /> : <StatusPill status="draft" />}</td></tr>)}</tbody></table></div>
        </Panel>
        <Panel title={t("dq.metrics")} subtitle={t("dq.metricsDetail")}>
          <div className="metric-catalog">{metrics.data.items.map((metric) => <article key={metric.code}><div><strong>{formatMetricLabel(metric.code, metric.label, language)}</strong><span>{metric.code} · v{metric.version}</span></div><BasisBadge basis={metric.basis} interactive={metric.basis !== "derived"} />{metric.formula ? <code>{metric.formula}</code> : null}{metric.unavailable_reason ? <p>{formatMetricReason(metric.code, metric.unavailable_reason, language)}</p> : null}</article>)}</div>
        </Panel>
      </div>
      <GenericDatasetIssues datasets={genericDatasets.data?.items ?? []} term={term} severity={severity} language={language} />
      <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.code ?? t("dq.drawer")} subtitle={selected ? humanize(selected.severity, language) : undefined}>
        {selected ? <div className="drawer-stack"><div className="alert-banner alert-banner--danger"><AlertOctagon /><div><strong>{selected.message}</strong><p>{t("dq.affectedFields", { fields: selected.affected_fields.map((field) => humanize(field, language)).join(", ") || t("dq.portfolio") })}</p></div></div><div className="drawer-section"><h3>{t("cash.sourceEvidence")}</h3><p>{language === "en" ? "Raw business rows are preserved unchanged; the exact workbook is available from its upload." : "Необработанные бизнес-строки хранятся неизменно, а точную рабочую книгу можно получить из её загрузки."}</p></div>{selected.source_refs.length ? selected.source_refs.map((source, index) => {
          const key = `${source.sheet_name}-${source.row_number}-${index}`;
          const content = <><strong>{source.workbook_name}</strong><span>{dqSourceLocation(source, language)}</span></>;
          const cell = source.source_cells?.[0];
          if (source.source_row_id && cell) {
            const reference: SourceReferenceWithUpload = {
              source_kind: "row",
              source_row_id: source.source_row_id,
              source_cell: cell,
              sheet_name: source.sheet_name,
              workbook_name: source.workbook_name,
              parser_version: "",
            };
            return <button type="button" className="evidence-row evidence-row--button" key={key} onClick={() => openSourcePreview(reference)} aria-label={language === "en" ? `Open cell ${cell}` : `Открыть ячейку ${cell}`}>{content}</button>;
          }
          return <div className="evidence-row" key={key}>{content}</div>;
        }) : <div className="evidence-row"><strong>{t("dq.portfolioRule")}</strong><span>{t("dq.portfolioRuleDetail")}</span></div>}{selected.acknowledgement ? <div className="ack-card"><strong>{t("dq.acknowledgedBy", { actor: selected.acknowledgement.actor_id })}</strong><span>{selected.acknowledgement.comment}</span><small>{formatDate(selected.acknowledgement.acknowledged_at.slice(0, 10), language)}</small></div> : <div className="unavailable-note">{t("dq.notAcknowledged")}</div>}
          <div className="drawer-section">
            <h3><UserCog aria-hidden="true" className="table-icon" /> {t("dq.remediation")}</h3>
            <p>{selected.owner_id ? <>{t("dq.assigned", { owner: selected.owner_id })}{selected.due_date ? <> · {t("dq.byDate", { date: formatDate(selected.due_date, language) })}</> : null}{selected.is_overdue ? <> · <StatusPill status="overdue" /></> : null}</> : t("dq.notAssigned")}</p>
            <div className="assignment-form">
              <label>{t("dq.ownerInput")}<input value={ownerId} onChange={(event) => setOwnerId(event.target.value)} placeholder={t("dq.ownerPlaceholder")} maxLength={200} /></label>
              <label>{t("dq.dueDate")}<input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} disabled={!ownerId.trim()} /></label>
              <label>{t("dq.reason")}<textarea value={assignReason} onChange={(event) => setAssignReason(event.target.value)} placeholder={t("dq.reasonPlaceholder")} maxLength={4000} /></label>
              {assignError ? <div className="inline-error" role="alert">{assignError}</div> : null}
              <button
                className="button button--primary"
                type="button"
                disabled={assign.isPending || !assignReason.trim()}
                onClick={() => assign.mutate({ ownerId: ownerId.trim() || null, dueDate: ownerId.trim() ? (dueDate || null) : null, reason: assignReason })}
              >
                {assign.isPending ? t("common.save") : ownerId.trim() || !selected.owner_id ? t("dq.assign") : t("dq.unassign")}
              </button>
            </div>
          </div>
        </div> : null}
      </Drawer>
    </PageFrame>
  );
}

function dqSourceLocation(source: {
  sheet_name: string;
  row_number: number;
  source_columns?: string[];
  source_cells?: string[];
}, language: "ru" | "en") {
  const row = language === "en" ? `row ${source.row_number}` : `строка ${source.row_number}`;
  const cells = source.source_cells?.length ? `${language === "en" ? "cells" : "ячейки"} ${source.source_cells.join(", ")}` : source.source_columns?.length ? `${language === "en" ? "columns" : "столбцы"} ${source.source_columns.join(", ")}` : "";
  return [source.sheet_name, row, cells].filter(Boolean).join(" · ");
}

function GenericDatasetIssues({ datasets, term, severity, language }: { datasets: DatasetVersion[]; term: string; severity: string; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const normalized = term.trim().toLocaleLowerCase();
  const rows = datasets.flatMap((dataset) => dataset.issues.map((issue) => ({ dataset, issue }))).filter(({ issue }) => (severity === "all" || issue.severity === severity) && (!normalized || [issue.code, issue.message, ...issue.affected_fields].some((value) => value.toLocaleLowerCase().includes(normalized))));
  return <Panel title={l("Замечания других источников", "Other source findings")} subtitle={l("Замечания привязаны к независимой версии набора и исходному файлу.", "Findings are tied to an independent dataset version and source file.")}>
    {rows.length ? <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Правило", "Rule")}</th><th>{l("Серьёзность", "Severity")}</th><th>{l("Набор / область", "Dataset / scope")}</th><th>{l("Замечание", "Finding")}</th><th>{l("Рабочая книга", "Workbook")}</th><th>{l("Исходное место", "Source location")}</th></tr></thead><tbody>{rows.map(({ dataset, issue }) => <tr key={issue.id}><td><strong>{issue.code}</strong></td><td><StatusPill status={issue.severity} /></td><td>{dataset.dataset_type}<small>{dataset.scope_code} · v{dataset.version}</small></td><td>{issue.message}</td><td>{dataset.source_filename}</td><td>{issue.source_refs.map((source) => `${String(source.sheet_name ?? "—")}:${String(source.row_number ?? "—")}`).join(", ") || "—"}</td></tr>)}</tbody></table></div> : <EmptyState title={l("Замечаний других источников нет", "No other source findings")} detail={l("Загрузите и разберите дополнительные рабочие книги либо измените фильтр.", "Upload and parse additional workbooks or change the filter.")} />}
  </Panel>;
}
