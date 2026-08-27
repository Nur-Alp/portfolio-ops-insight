import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeftRight } from "lucide-react";
import { useSearch } from "@tanstack/react-router";
import type { CashBalance, DataQualityIssue, MetricValue } from "../api/types";
import { dashboardApi } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { Panel } from "../components/ui/Panel";
import { StatusPill } from "../components/ui/StatusPill";
import { usePortfolioSnapshot } from "../hooks/usePortfolioSnapshot";
import { formatAssetClass, formatDate, formatKzt, formatMetricLabel, formatPercent, formatReportDate, humanize } from "../lib/format";
import { useI18n, type AppLanguage } from "../i18n";
import type { DashboardSearch } from "../router";
import { PageFrame } from "../components/ui/PageFrame";

// v1 deliberately compares only each portfolio's latest published snapshot
// (no historical/other-version picker) and always uses the derived-carrying
// basis for allocation, since this route has no shared filterbar of its own.
// If shareable/bookmarkable comparison links are wanted later, add optional
// compareA/compareB fields to DashboardSearch (router.tsx) following the
// same `allowed()` validator pattern already used for basis/currency, and
// seed codeA/codeB from those instead of local useState.

const KPI_METRIC_CODES = [
  "position_count",
  "unique_isin_count",
  "purchase_amount_kzt",
  "derived_carrying_value_kzt",
  "cash_kzt",
  "derived_operational_total_kzt",
  "total_fees_kzt",
  "total_reserves_kzt",
  "official_nav_kzt",
  "official_performance"
] as const;

const GATE_KEYS = ["independent_approval", "critical_dq_acknowledged", "published"] as const;
const SEVERITIES = ["blocker", "high", "medium", "low"] as const;

function useSideData(snapshotId: string) {
  const overview = useQuery({ queryKey: ["overview", snapshotId], queryFn: () => dashboardApi.overview(snapshotId), enabled: Boolean(snapshotId) });
  const allocation = useQuery({ queryKey: ["allocation", snapshotId, "asset_class", "derived_carrying"], queryFn: () => dashboardApi.allocation(snapshotId, "asset_class", "derived_carrying"), enabled: Boolean(snapshotId) });
  const cash = useQuery({ queryKey: ["cash", snapshotId], queryFn: () => dashboardApi.cash(snapshotId), enabled: Boolean(snapshotId) });
  const issues = useQuery({ queryKey: ["issues", snapshotId], queryFn: () => dashboardApi.issues(snapshotId), enabled: Boolean(snapshotId) });
  const readiness = useQuery({ queryKey: ["readiness", snapshotId], queryFn: () => dashboardApi.readiness(snapshotId), enabled: Boolean(snapshotId) });
  return { overview, allocation, cash, issues, readiness };
}

function cashTotals(items: CashBalance[]) {
  const byCurrency = new Map<string, { native: number; kzt: number }>();
  let totalKzt = 0;
  for (const item of items) {
    if (!item.active) continue;
    const current = byCurrency.get(item.currency) ?? { native: 0, kzt: 0 };
    current.native += Number(item.native_amount);
    current.kzt += Number(item.kzt_amount);
    byCurrency.set(item.currency, current);
    totalKzt += Number(item.kzt_amount);
  }
  return { byCurrency, totalKzt };
}

function severityCounts(items: DataQualityIssue[]): Record<string, number> {
  return items.reduce<Record<string, number>>((result, issue) => ({ ...result, [issue.severity]: (result[issue.severity] ?? 0) + 1 }), {});
}

function formatMetricValue(code: string, metric: MetricValue | undefined, language: AppLanguage, unavailableLabel: string): string {
  if (!metric || metric.basis === "unavailable" || metric.value === null) return unavailableLabel;
  if (code.endsWith("_kzt")) return formatKzt(metric.value, language);
  return Number(metric.value).toLocaleString(language === "en" ? "en-GB" : "ru-RU");
}

function computeDelta(metricA: MetricValue | undefined, metricB: MetricValue | undefined): { delta: number | null; deltaPercent: number | null } {
  if (!metricA || !metricB || metricA.basis === "unavailable" || metricB.basis === "unavailable" || metricA.value === null || metricB.value === null) {
    return { delta: null, deltaPercent: null };
  }
  const valueA = Number(metricA.value);
  const valueB = Number(metricB.value);
  const delta = valueB - valueA;
  return { delta, deltaPercent: valueA !== 0 ? (delta / valueA) * 100 : null };
}

function formatDeltaValue(code: string, delta: number | null, language: AppLanguage, unavailableLabel: string): string {
  if (delta === null) return unavailableLabel;
  const sign = delta > 0 ? "+" : "";
  if (code.endsWith("_kzt")) return `${sign}${formatKzt(delta, language)}`;
  return `${sign}${delta.toLocaleString(language === "en" ? "en-GB" : "ru-RU")}`;
}

export function ComparisonPage() {
  const { language, t } = useI18n();
  const search = useSearch({ strict: false }) as DashboardSearch;
  const portfolios = useQuery({ queryKey: ["portfolios"], queryFn: dashboardApi.portfolios });
  const [codeA, setCodeA] = useState(search.portfolio);
  const [codeB, setCodeB] = useState("");

  useEffect(() => {
    if (!codeB && portfolios.data) {
      setCodeB(portfolios.data.items.find((item) => item.code !== codeA)?.code ?? codeA);
    }
  }, [portfolios.data, codeA, codeB]);

  const sideA = usePortfolioSnapshot(codeA);
  const sideB = usePortfolioSnapshot(codeB);
  const dataA = useSideData(sideA.snapshotId);
  const dataB = useSideData(sideB.snapshotId);

  const allocationRows = useMemo(() => {
    const itemsA = dataA.allocation.data?.items ?? [];
    const itemsB = dataB.allocation.data?.items ?? [];
    const labels = new Set([...itemsA.map((item) => item.label), ...itemsB.map((item) => item.label)]);
    return [...labels].sort().map((label) => ({
      label,
      // A label absent from one side's allocation means that portfolio holds
      // none of that asset class, not that the value is unknown - 0%, not unavailable.
      weightA: itemsA.find((item) => item.label === label)?.weight_percent ?? "0",
      weightB: itemsB.find((item) => item.label === label)?.weight_percent ?? "0"
    }));
  }, [dataA.allocation.data, dataB.allocation.data]);

  const severityA = useMemo(() => severityCounts(dataA.issues.data?.items ?? []), [dataA.issues.data]);
  const severityB = useMemo(() => severityCounts(dataB.issues.data?.items ?? []), [dataB.issues.data]);
  const cashA = useMemo(() => cashTotals(dataA.cash.data?.items ?? []), [dataA.cash.data]);
  const cashB = useMemo(() => cashTotals(dataB.cash.data?.items ?? []), [dataB.cash.data]);
  const cashCurrencies = useMemo(
    () => [...new Set([...cashA.byCurrency.keys(), ...cashB.byCurrency.keys()])].sort(),
    [cashA, cashB]
  );

  if (portfolios.isLoading) return <LoadingState label={language === "en" ? "Loading portfolio registry" : "Загрузка реестра портфелей"} />;
  if (portfolios.error) return <ErrorState error={portfolios.error} retry={() => portfolios.refetch()} />;

  const unavailable = t("common.unavailable");
  const swap = () => {
    setCodeA(codeB);
    setCodeB(codeA);
  };

  const identitySide = (code: string, snapshotId: string, portfolioName: string | undefined, overview: ReturnType<typeof useSideData>["overview"]) => (
    <div className="comparison-identity__side">
      <h3>{code}{portfolioName ? ` · ${portfolioName}` : ""}</h3>
      {!snapshotId ? (
        <EmptyState title={t("comparison.noSnapshot")} detail={t("comparison.noSnapshotDetail")} />
      ) : overview.data ? (
        <dl>
          <div><dt>{language === "en" ? "Report date" : "Отчётная дата"}</dt><dd>{formatDate(overview.data.report_date, language)}</dd></div>
          <div><dt>{language === "en" ? "Version" : "Версия"}</dt><dd>{overview.data.version}</dd></div>
          <div><dt>{language === "en" ? "Status" : "Статус"}</dt><dd><StatusPill status={overview.data.status} /></dd></div>
        </dl>
      ) : overview.isLoading ? (
        <LoadingState />
      ) : null}
    </div>
  );

  return (
    <PageFrame title={t("comparison.title")} eyebrow={t("comparison.eyebrow")} description={t("comparison.description")}>
      <div className="comparison-picker" role="group" aria-label={t("comparison.title")}>
        <label>
          <span>{t("comparison.portfolioA")}</span>
          <select value={codeA} onChange={(event) => setCodeA(event.target.value)}>
            {(portfolios.data?.items ?? []).map((portfolio) => (
              <option key={portfolio.code} value={portfolio.code}>
                {portfolio.code} · {formatReportDate(portfolio.latest_published_report_date, language)}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="icon-button comparison-picker__swap" aria-label={t("comparison.swap")} onClick={swap}>
          <ArrowLeftRight aria-hidden="true" />
        </button>
        <label>
          <span>{t("comparison.portfolioB")}</span>
          <select value={codeB} onChange={(event) => setCodeB(event.target.value)}>
            {(portfolios.data?.items ?? []).map((portfolio) => (
              <option key={portfolio.code} value={portfolio.code}>
                {portfolio.code} · {formatReportDate(portfolio.latest_published_report_date, language)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {codeA && codeB && codeA === codeB ? (
        <div className="alert-banner alert-banner--warning">
          <AlertTriangle aria-hidden="true" />
          <div><strong>{t("comparison.samePortfolio")}</strong></div>
        </div>
      ) : null}

      <Panel title={t("comparison.identityTitle")} subtitle={t("comparison.identityDetail")}>
        <div className="comparison-identity">
          {identitySide(codeA, sideA.snapshotId, sideA.portfolio?.name, dataA.overview)}
          {identitySide(codeB, sideB.snapshotId, sideB.portfolio?.name, dataB.overview)}
        </div>
      </Panel>

      <Panel title={t("comparison.kpiTitle")} subtitle={t("comparison.kpiSubtitle")}>
        {sideA.snapshotId && sideB.snapshotId ? (
          dataA.overview.data && dataB.overview.data ? (
            <div className="table-scroll" tabIndex={0}>
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>{t("comparison.metric")}</th>
                    <th>{codeA}</th>
                    <th>{codeB}</th>
                    <th>{t("comparison.delta")}</th>
                    <th>{t("comparison.deltaPercent")}</th>
                  </tr>
                </thead>
                <tbody>
                  {KPI_METRIC_CODES.map((code) => {
                    const metricA = dataA.overview.data!.metrics[code];
                    const metricB = dataB.overview.data!.metrics[code];
                    const { delta, deltaPercent } = computeDelta(metricA, metricB);
                    const deltaTone = delta === null ? "" : delta > 0 ? "comparison-table__delta--positive" : delta < 0 ? "comparison-table__delta--negative" : "";
                    return (
                      <tr key={code}>
                        <td>{formatMetricLabel(code, code, language)}</td>
                        <td>{formatMetricValue(code, metricA, language, unavailable)}</td>
                        <td>{formatMetricValue(code, metricB, language, unavailable)}</td>
                        <td className={deltaTone}>{formatDeltaValue(code, delta, language, unavailable)}</td>
                        <td className={deltaTone}>{deltaPercent === null ? unavailable : formatPercent(deltaPercent, 1, language)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <LoadingState />
          )
        ) : (
          <EmptyState title={t("comparison.noSnapshot")} detail={t("comparison.noSnapshotDetail")} />
        )}
      </Panel>

      <Panel title={t("comparison.allocationTitle")} subtitle={t("comparison.allocationBasisNote")}>
        {sideA.snapshotId && sideB.snapshotId ? (
          dataA.allocation.data && dataB.allocation.data ? (
            <div className="table-scroll" tabIndex={0}>
              <table className="comparison-table">
                <thead><tr><th>{t("holding.class")}</th><th>{codeA}</th><th>{codeB}</th></tr></thead>
                <tbody>
                  {allocationRows.map((row) => (
                    <tr key={row.label}>
                      <td>{formatAssetClass(row.label, language)}</td>
                      <td>{formatPercent(row.weightA, 1, language)}</td>
                      <td>{formatPercent(row.weightB, 1, language)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <LoadingState />
          )
        ) : (
          <EmptyState title={t("comparison.noSnapshot")} detail={t("comparison.noSnapshotDetail")} />
        )}
      </Panel>

      <div className="content-grid content-grid--two-thirds">
        <Panel title={t("comparison.dqTitle")} subtitle={t("comparison.dqSubtitle")}>
          {sideA.snapshotId && sideB.snapshotId ? (
            dataA.issues.data && dataB.issues.data && dataA.readiness.data && dataB.readiness.data ? (
              <table className="comparison-table">
                <thead><tr><th>{t("dq.severity")}</th><th>{codeA}</th><th>{codeB}</th></tr></thead>
                <tbody>
                  {SEVERITIES.map((severity) => (
                    <tr key={severity}>
                      <td><StatusPill status={severity} /></td>
                      <td>{severityA[severity] ?? 0}</td>
                      <td>{severityB[severity] ?? 0}</td>
                    </tr>
                  ))}
                  <tr>
                    <td>{t("comparison.unacknowledgedCritical")}</td>
                    <td>{dataA.readiness.data.unacknowledged_critical_count}</td>
                    <td>{dataB.readiness.data.unacknowledged_critical_count}</td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <LoadingState />
            )
          ) : (
            <EmptyState title={t("comparison.noSnapshot")} detail={t("comparison.noSnapshotDetail")} />
          )}
        </Panel>

        <Panel title={t("comparison.governanceTitle")} subtitle={t("comparison.governanceDetail")}>
          {sideA.snapshotId && sideB.snapshotId ? (
            dataA.readiness.data && dataB.readiness.data ? (
              <table className="comparison-table">
                <thead><tr><th>{t("comparison.check")}</th><th>{codeA}</th><th>{codeB}</th></tr></thead>
                <tbody>
                  <tr>
                    <td>{t("comparison.snapshotStatus")}</td>
                    <td><StatusPill status={dataA.readiness.data.status} /></td>
                    <td><StatusPill status={dataB.readiness.data.status} /></td>
                  </tr>
                  {GATE_KEYS.map((gate) => (
                    <tr key={gate}>
                      <td>{humanize(gate, language)}</td>
                      <td><StatusPill status={dataA.readiness.data!.gates[gate] ? "published" : "failed"} /></td>
                      <td><StatusPill status={dataB.readiness.data!.gates[gate] ? "published" : "failed"} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <LoadingState />
            )
          ) : (
            <EmptyState title={t("comparison.noSnapshot")} detail={t("comparison.noSnapshotDetail")} />
          )}
        </Panel>
      </div>

      <Panel title={t("comparison.cashTitle")} subtitle={t("comparison.cashSubtitle")}>
        {sideA.snapshotId && sideB.snapshotId ? (
          dataA.cash.data && dataB.cash.data ? (
            <>
              <div className="comparison-total-cash">
                <span>{t("comparison.totalCash")}</span>
                <div className="comparison-total-cash__values">
                  <div><strong>{codeA}</strong><span>{formatKzt(cashA.totalKzt, language)}</span></div>
                  <div><strong>{codeB}</strong><span>{formatKzt(cashB.totalKzt, language)}</span></div>
                </div>
              </div>
              <div className="table-scroll" tabIndex={0}>
                <table className="comparison-table">
                  <thead><tr><th>{t("comparison.currency")}</th><th>{codeA} ({t("comparison.native")})</th><th>{codeA} (KZT)</th><th>{codeB} ({t("comparison.native")})</th><th>{codeB} (KZT)</th></tr></thead>
                  <tbody>
                    {cashCurrencies.map((currency) => {
                      const valuesA = cashA.byCurrency.get(currency);
                      const valuesB = cashB.byCurrency.get(currency);
                      return (
                        <tr key={currency}>
                          <td>{currency}</td>
                          <td>{valuesA ? valuesA.native.toLocaleString(language === "en" ? "en-GB" : "ru-RU", { maximumFractionDigits: 0 }) : unavailable}</td>
                          <td>{valuesA ? formatKzt(valuesA.kzt, language) : unavailable}</td>
                          <td>{valuesB ? valuesB.native.toLocaleString(language === "en" ? "en-GB" : "ru-RU", { maximumFractionDigits: 0 }) : unavailable}</td>
                          <td>{valuesB ? formatKzt(valuesB.kzt, language) : unavailable}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <LoadingState />
          )
        ) : (
          <EmptyState title={t("comparison.noSnapshot")} detail={t("comparison.noSnapshotDetail")} />
        )}
      </Panel>

      <Panel title={t("comparison.notIncludedTitle")}>
        <p>{t("comparison.notIncludedDetail")}</p>
      </Panel>
    </PageFrame>
  );
}
