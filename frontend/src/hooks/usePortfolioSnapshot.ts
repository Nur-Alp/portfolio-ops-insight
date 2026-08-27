import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../api/client";

export function usePortfolioSnapshot(code: string) {
  const portfolios = useQuery({ queryKey: ["portfolios"], queryFn: dashboardApi.portfolios });
  const portfolio = portfolios.data?.items.find((item) => item.code === code);
  return {
    portfolios,
    portfolio,
    snapshotId: portfolio?.latest_published_snapshot_id ?? ""
  };
}
