import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, FileCheck2, LockKeyhole, ShieldCheck } from "lucide-react";
import { dashboardApi } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { BasisBadge } from "../components/ui/BasisBadge";
import { KpiCard } from "../components/ui/KpiCard";
import { Panel } from "../components/ui/Panel";
import { StatusPill } from "../components/ui/StatusPill";
import { useSelectedSnapshot } from "../hooks/useSelectedSnapshot";
import { formatDate, humanize } from "../lib/format";
import { useI18n } from "../i18n";
import { PageFrame } from "../components/ui/PageFrame";

export function ReportingPage() {
  const { language, t } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const queryClient = useQueryClient();
  const selectedSnapshot = useSelectedSnapshot();
  const { search, portfolios, snapshotId } = selectedSnapshot;
  const osipEnabled = selectedSnapshot.osipEnabled ?? Boolean(snapshotId);
  const readiness = useQuery({ queryKey: ["readiness", snapshotId], queryFn: () => dashboardApi.readiness(snapshotId), enabled: Boolean(snapshotId) });
  const reports = useQuery({ queryKey: ["reports", snapshotId], queryFn: () => dashboardApi.reports(snapshotId), enabled: Boolean(snapshotId) });
  const generate = useMutation({ mutationFn: () => dashboardApi.createReport(snapshotId), onSuccess: async (report) => { await queryClient.invalidateQueries({ queryKey: ["reports", snapshotId] }); await dashboardApi.downloadReport(report); } });
  if (!osipEnabled) return <PageFrame title={l("Экспорт OSIP", "OSIP operational export")} eyebrow={l("OSIP / Операционный вывод", "OSIP / operational output")} description={l("Операционный вывод OSIP доступен только в области Бэк офиса.", "The OSIP operational output is available only in the Back Office domain.")}><EmptyState title={l("Раздел не относится к текущей области", "This section is outside the current domain")} detail={l("Переключитесь на Бэк офис, чтобы открыть контролируемый вывод портфеля.", "Switch to Back Office to open the controlled portfolio output.")} /></PageFrame>;
  if (portfolios.isLoading || readiness.isLoading) return <LoadingState label={l("Проверка контролей отчётности", "Checking reporting controls")} />;
  const error = portfolios.error ?? readiness.error;
  if (error) return <ErrorState error={error} />;
  if (!snapshotId || !readiness.data) return <PageFrame title={l("Экспорт OSIP", "OSIP operational export")} eyebrow={l("OSIP / Операционный вывод", "OSIP / operational output")} description={l("Готовность опубликованной версии портфеля и контролируемый вывод.", "Published portfolio readiness and controlled output.")}><EmptyState title={t("holding.noPublished")} detail={l(`Опубликуйте ${search.portfolio}, прежде чем сформировать пакет операционного вывода.`, `Publish ${search.portfolio} before generating an operational package.`)} /></PageFrame>;
  const report = readiness.data;
  const passed = Object.values(report.gates).filter(Boolean).length;
  return (
    <PageFrame title={l("Экспорт OSIP", "OSIP operational export")} eyebrow={l("OSIP / Контроли операционного вывода", "OSIP / operational output controls")} description={l("Операционный пакет — это утверждённый пакет версии портфеля, а не неконтролируемая выгрузка.", "The operational package is an approved portfolio-version package, not an uncontrolled extract.")} meta={<><StatusPill status={report.status} /><span>{t("overview.asOf", { date: formatDate(report.report_date, language) })}</span><span>{t("filter.version", { value: report.version })}</span></>}>
      <div className="kpi-grid">
        <KpiCard label={l("Операционная готовность", "Operational readiness")} value={report.operational_snapshot_export.ready ? l("Готово", "Ready") : l("Заблокировано", "Blocked")} basis="derived" tone={report.operational_snapshot_export.ready ? "positive" : "danger"} icon={<FileCheck2 />} />
        <KpiCard label={l("Контроли проверки", "Assurance controls")} value={`${passed}/${Object.keys(report.gates).length}`} basis="source" icon={<ShieldCheck />} />
        <KpiCard label={t("overview.critical")} value={String(report.critical_dq_count)} basis="source" detail={l(`${report.unacknowledged_critical_count} не подтверждено`, `${report.unacknowledged_critical_count} not acknowledged`)} />
        <KpiCard label={l("Официальный отчёт", "Official report")} value={t("common.unavailable")} basis="unavailable" tone="warning" icon={<LockKeyhole />} />
      </div>
      <div className="content-grid content-grid--two-thirds">
        <Panel title={l("Пакет операционной версии", "Operational-version package")} subtitle={l("Подтверждения рабочей книги, канонические данные, замечания DQ и данные утверждения", "Workbook evidence, canonical data, DQ findings, and approval details")}>
          <div className="gate-list">{Object.entries(report.gates).map(([name, value]) => <div key={name}><span className={`gate-icon ${value ? "gate-icon--pass" : "gate-icon--fail"}`}>{value ? <CheckCircle2 /> : <LockKeyhole />}</span><div><strong>{humanize(name, language)}</strong><p>{value ? l("Контроль выполнен для этой версии портфеля.", "This control has passed for this portfolio version.") : l("Этот контроль не позволяет выполнить операционный экспорт.", "This control prevents operational export.")}</p></div><StatusPill status={value ? "approved" : "failed"} /></div>)}</div>
          {report.operational_snapshot_export.blocking_reasons.length ? <div className="inline-error">{report.operational_snapshot_export.blocking_reasons.join(" ")}</div> : <div className="report-ready-action"><div className="alert-banner alert-banner--success"><CheckCircle2 /><div><strong>{l("Операционный пакет можно сформировать", "The operational package can be generated")}</strong><p>{l("CSV адресуется по содержимому, воспроизводим и привязан к утверждённой версии портфеля.", "The CSV is content-addressed, reproducible, and tied to the approved portfolio version.")}</p></div></div><button className="button button--primary" type="button" disabled={generate.isPending} onClick={() => generate.mutate()}><Download /> {generate.isPending ? l("Формирование…", "Generating…") : l("Сформировать и скачать CSV", "Generate and download CSV")}</button>{generate.error ? <div className="inline-error">{generate.error.message}</div> : null}</div>}
        </Panel>
        <Panel title={l("Политика вывода", "Output policy")} subtitle={l("Доступные и недоступные классы отчётов", "Available and unavailable report classes")}>
          <div className="report-class"><div><strong>{l("Операционная версия портфеля OSIP", "OSIP operational portfolio version")}</strong><span>{l("Позиции, денежные средства, датированные события, DQ и раскрытие источника", "Holdings, cash, dated events, DQ, and source disclosure")}</span></div><BasisBadge basis="derived" interactive={false} /></div>
          <div className="report-class"><div><strong>{l("Официальный NAV / доходность", "Official NAV / performance")}</strong><span>{report.official_report_export.blocking_reasons[0]}</span></div><BasisBadge basis="unavailable" /></div>
        </Panel>
      </div>
      <Panel title={l("Идентичность версии", "Version identity")} subtitle={l("Каждый последующий артефакт сохранит эту неизменяемую идентичность публикации", "Every subsequent artifact retains this immutable publication identity")}>
        <dl className="identity-grid"><div><dt>{t("filter.portfolio")}</dt><dd>{report.portfolio}</dd></div><div><dt>{l("Отчётная дата", "Report date")}</dt><dd>{report.report_date}</dd></div><div><dt>{l("Версия портфеля", "Portfolio version")}</dt><dd>{report.version}</dd></div><div><dt>{l("Идентификатор загрузки", "Upload ID")}</dt><dd>{report.import_id}</dd></div></dl>
        {reports.data?.items.length ? <div className="artifact-list">{reports.data.items.map((artifact) => <button type="button" key={artifact.id} onClick={() => dashboardApi.downloadReport(artifact)}><FileCheck2 /><span><strong>{l("Операционная версия портфеля CSV", "Operational portfolio version CSV")}</strong><small>{artifact.artifact_sha256.slice(0, 16)}… · {artifact.requested_by}</small></span><Download /></button>)}</div> : null}
      </Panel>
    </PageFrame>
  );
}
