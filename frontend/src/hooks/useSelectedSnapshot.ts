import { useQuery } from "@tanstack/react-query";
import { useSearch } from "@tanstack/react-router";
import { dashboardApi } from "../api/client";
import { getCurrentDomainScope } from "../auth/session";
import type { DashboardSearch } from "../router";

export function useSelectedSnapshot() {
  const search = useSearch({ strict: false }) as DashboardSearch;
  const domainScope = getCurrentDomainScope();
  const osipEnabled = domainScope === "*" || domainScope === "back_office";
  const portfolios = useQuery({ queryKey: ["portfolios", domainScope], queryFn: dashboardApi.portfolios, enabled: osipEnabled });
  const portfolio = portfolios.data?.items.find((item) => item.code === search.portfolio);
  const snapshots = useQuery({
    queryKey: ["snapshots", search.portfolio, "history", domainScope],
    queryFn: () => dashboardApi.snapshots(search.portfolio, true),
    enabled: osipEnabled && Boolean(search.portfolio)
  });
  const selectedSnapshot = snapshots.data?.items.find((item) => item.id === search.snapshot);
  return {
    search,
    portfolios,
    portfolio,
    osipEnabled,
    snapshots,
    snapshotId: selectedSnapshot?.id ?? portfolio?.latest_published_snapshot_id ?? ""
  };
}
