import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AlertTriangle, CalendarDays, CheckCircle2, Layers3, Scale, WalletCards } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import { dashboardApi } from "../api/client";
import { formatAssetClass, formatDate, formatKzt, humanize } from "../lib/format";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { BasisBadge } from "../components/ui/BasisBadge";
import { ExcludedLotsDrawer } from "../components/ui/ExcludedLotsDrawer";
import { KpiCard } from "../components/ui/KpiCard";
import { Panel } from "../components/ui/Panel";
import { StatusPill } from "../components/ui/StatusPill";
import { ProvenanceDrawer } from "../components/ui/ProvenanceDrawer";
import { useProvenance } from "../components/ui/ProvenanceContext";
import { SourceRowLegend } from "../components/ui/SourceRowLegend";
import { PageFrame } from "../components/ui/PageFrame";
import { useSelectedSnapshot } from "../hooks/useSelectedSnapshot";
import { useI18n } from "../i18n";
import { TableSearch } from "../components/ui/TableSearch";

export function OverviewPage() {
  const { language, t } = useI18n();
  const { openSourcePreview } = useProvenance();
  const navigate = useNavigate();
  const { search, portfolios, snapshotId } = useSelectedSnapshot();
  const overview = useQuery({
    queryKey: ["overview", snapshotId],
    queryFn: () => dashboardApi.overview(snapshotId),
    enabled: Boolean(snapshotId)
  });
  const allocation = useQuery({
    queryKey: ["allocation", snapshotId, "asset_class", search.basis],
    queryFn: () => dashboardApi.allocation(snapshotId, "asset_class", search.basis),
    enabled: Boolean(snapshotId)
  });
  const calendar = useQuery({
    queryKey: ["calendar", snapshotId],
    queryFn: () => dashboardApi.calendar(snapshotId),
    enabled: Boolean(snapshotId)
  });
  const readiness = useQuery({
    queryKey: ["readiness", snapshotId],
    queryFn: () => dashboardApi.readiness(snapshotId),
    enabled: Boolean(snapshotId)
  });
  const provenance = useQuery({
    queryKey: ["provenance", snapshotId],
    queryFn: () => dashboardApi.provenance(snapshotId),
    enabled: Boolean(snapshotId)
  });
  const [provenanceCode, setProvenanceCode] = useState<string | null>(null);
  const [excludedLotsOpen, setExcludedLotsOpen] = useState(false);

  if (portfolios.isLoading) return <LoadingState label={language === "en" ? "Loading portfolio registry" : "Загрузка реестра портфелей"} />;
  if (portfolios.error) return <ErrorState error={portfolios.error} retry={() => portfolios.refetch()} />;
  if (!snapshotId) {
    return (
      <PageFrame title={t("overview.title")} eyebrow="OSIP / Portfolio as of date" description={language === "en" ? "Approved portfolio values, data provenance, and operational warnings." : "Утверждённые значения портфеля, происхождение данных и операционные предупреждения."}>
        <EmptyState
          title={`${t("holding.noPublished")}: ${search.portfolio}`}
          detail={language === "en" ? "Upload, validate, independently approve, and publish an OSIP workbook to view data." : "Загрузите, проверьте, независимо утвердите и опубликуйте рабочую книгу OSIP, чтобы увидеть данные."}
        />
      </PageFrame>
    );
  }
  if (overview.isLoading || allocation.isLoading || calendar.isLoading || readiness.isLoading || provenance.isLoading) {
    return <LoadingState />;
  }
  const firstError = overview.error ?? allocation.error ?? calendar.error ?? readiness.error ?? provenance.error;
  if (firstError) return <ErrorState error={firstError} />;
  if (!overview.data || !allocation.data || !calendar.data || !readiness.data || !provenance.data) return null;

  const metric = overview.data.metrics;
  const upcoming = calendar.data.items.filter((event) => event.status !== "historical").slice(0, 7);
  // A lot missing its carrying amount used to blank the entire portfolio's
  // derived total; it's now excluded and disclosed here instead, so one
  // incomplete deposit row doesn't hide every other lot's real numbers. A
  // button rather than caption text: the count is always short regardless
  // of how many lots are excluded. It opens ExcludedLotsDrawer - a focused
  // view of just what's missing and why - rather than the full metric
  // provenance drawer, which shows every included lot's own references too
  // and buries the excluded ones among them.
  const excludedLotCount = overview.data.excluded_lot_count;
  return (
    <PageFrame
      title={t("overview.title")}
      eyebrow={t("overview.eyebrow")}
      description={t("overview.description")}
      meta={
        <>
          <StatusPill status={overview.data.status} />
          <span>{t("overview.asOf", { date: formatDate(overview.data.report_date, language) })}</span>
          <span>{t("filter.version", { value: overview.data.version })}</span>
          <button type="button" className="button button--secondary" onClick={() => navigate({ to: "/comparison", search })}>
            <Scale aria-hidden="true" /> {t("overview.compareButton")}
          </button>
        </>
      }
    >
      <div className="kpi-grid">
        <KpiCard label={t("overview.currentLots")} value={String(metric.position_count.value)} basis="source" detail={t("overview.instruments", { count: metric.unique_isin_count.value ?? 0 })} icon={<Layers3 />} onBasisClick={() => setProvenanceCode("position_count")} />
        <KpiCard label={t("holding.purchase")} value={formatKzt(metric.purchase_amount_kzt.value, language)} basis="source" onBasisClick={() => setProvenanceCode("purchase_amount_kzt")} />
        <KpiCard label={t("overview.carrying")} value={formatKzt(metric.derived_carrying_value_kzt.value, language)} basis="derived" tone="positive" alertLabel={excludedLotCount > 0 ? t("overview.excludedLots", { count: excludedLotCount }) : undefined} onAlertClick={() => setExcludedLotsOpen(true)} onBasisClick={() => setProvenanceCode("derived_carrying_value_kzt")} />
        <KpiCard label={t("overview.cash")} value={formatKzt(metric.cash_kzt.value, language)} basis="source" icon={<WalletCards />} onBasisClick={() => setProvenanceCode("cash_kzt")} />
        <KpiCard label={t("overview.operationalTotal")} value={formatKzt(metric.derived_operational_total_kzt.value, language)} basis="derived" tone="positive" alertLabel={excludedLotCount > 0 ? t("overview.excludedLots", { count: excludedLotCount }) : undefined} onAlertClick={() => setExcludedLotsOpen(true)} onBasisClick={() => setProvenanceCode("derived_operational_total_kzt")} />
        <KpiCard label={t("overview.fees")} value={formatKzt(metric.total_fees_kzt.value, language)} basis="source" onBasisClick={() => setProvenanceCode("total_fees_kzt")} />
        <KpiCard label={t("overview.reserves")} value={formatKzt(metric.total_reserves_kzt.value, language)} basis="source" onBasisClick={() => setProvenanceCode("total_reserves_kzt")} />
        <KpiCard label={t("overview.officialNav")} value={t("common.unavailable")} basis="unavailable" tone="warning" onBasisClick={() => setProvenanceCode("official_nav_kzt")} />
      </div>

      {!readiness.data.operational_snapshot_export.ready ? (
        <div className="alert-banner alert-banner--danger">
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>{t("overview.exportBlocked")}</strong>
            <p>{readiness.data.operational_snapshot_export.blocking_reasons.join(" ")}</p>
          </div>
        </div>
      ) : (
        <div className="alert-banner alert-banner--success">
          <CheckCircle2 aria-hidden="true" />
          <div>
            <strong>{t("overview.controlsPass")}</strong>
            <p>{t("overview.controlsPassDetail")}</p>
          </div>
        </div>
      )}

      <div className="content-grid content-grid--two-thirds">
        <Panel
          title={t("overview.structure")}
          subtitle={t("overview.linkLots", { basis: allocation.data.value_basis === "purchase_amount_kzt" ? t("holding.purchase") : t("overview.carrying") })}
        >
          <div className="allocation-list">
            {allocation.data.items.map((item) => (
              <div className="allocation-row" key={item.label}>
                <div>
                  <strong>{formatAssetClass(item.label, language)}</strong>
                  <span>{item.lot_count} {t("holding.lots").toLowerCase()} · {t("overview.instruments", { count: item.instrument_count })}</span>
                </div>
                <div className="allocation-row__value">
                  <strong>{formatKzt(item.value_kzt, language)}</strong>
                  <span>{new Intl.NumberFormat(language === "en" ? "en-GB" : "ru-RU", { maximumFractionDigits: 1 }).format(Number(item.weight_percent))}%</span>
                </div>
                <div
                  className="progress-track"
                  role="progressbar"
                  aria-label={language === "en" ? `Weight of ${formatAssetClass(item.label, language)}` : `Доля ${formatAssetClass(item.label, language)}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.min(Number(item.weight_percent), 100)}
                >
                  <span style={{ width: `${Math.min(Number(item.weight_percent), 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title={t("overview.governance")} subtitle={t("overview.governanceDetail")}>
          <dl className="governance-list">
            {Object.entries(readiness.data.gates).map(([gate, passed]) => (
              <div key={gate}>
                <dt>{humanize(gate, language)}</dt>
                <dd><StatusPill status={passed ? "published" : "failed"} /></dd>
              </div>
            ))}
            <div><dt>{t("overview.critical")}</dt><dd>{readiness.data.critical_dq_count}</dd></div>
            <div><dt>{t("overview.officialReporting")}</dt><dd><BasisBadge basis="unavailable" /></dd></div>
          </dl>
        </Panel>
      </div>

      <Panel title={t("overview.calendar")} subtitle={t("overview.calendarDetail")} action={<div className="table-tools"><TableSearch label={language === "en" ? "Search portfolio events" : "Поиск событий портфеля"} placeholder={language === "en" ? "Date, event, instrument" : "Дата, событие, инструмент"} /><SourceRowLegend language={language} /></div>}>
        {upcoming.length ? (
          <div className="table-scroll" tabIndex={0}>
            <table className="clickable-table">
              <thead><tr><th>{language === "en" ? "Date" : "Дата"}</th><th>{language === "en" ? "Event" : "Событие"}</th><th>{t("holding.instrument")}</th><th>{language === "en" ? "Status" : "Статус"}</th></tr></thead>
              <tbody>
                {upcoming.map((event) => {
                  const source = event.source_refs[0];
                  const openable = Boolean(source?.source_cell);
                  return (
                    <tr
                      key={event.id}
                      tabIndex={openable ? 0 : undefined}
                      onClick={openable ? () => openSourcePreview(source) : undefined}
                      onKeyDown={openable ? (keyEvent) => { if (keyEvent.key === "Enter") openSourcePreview(source); } : undefined}
                      style={openable ? undefined : { cursor: "default" }}
                    >
                      <td>{formatDate(event.event_date, language)}</td>
                      <td><CalendarDays aria-hidden="true" className="table-icon" /> {humanize(event.event_type, language)}</td>
                      <td><strong>{event.security_code || event.isin}</strong><small>{event.isin}</small></td>
                      <td><StatusPill status={event.status} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <EmptyState title={t("overview.noEvents")} detail={t("overview.noEventsDetail")} />}
      </Panel>

      <ProvenanceDrawer metric={provenanceCode ? provenance.data.metrics[provenanceCode] ?? null : null} onClose={() => setProvenanceCode(null)} />
      <ExcludedLotsDrawer open={excludedLotsOpen} lots={overview.data.excluded_lots ?? []} excludedPurchaseValueKzt={overview.data.excluded_purchase_value_kzt} onClose={() => setExcludedLotsOpen(false)} />
    </PageFrame>
  );
}
