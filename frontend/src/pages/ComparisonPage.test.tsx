import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AllocationResponse, CashResponse, IssuesResponse, PortfolioListResponse, ReportReadiness, SnapshotOverview } from "../api/types";

afterEach(() => cleanup());

vi.mock("@tanstack/react-router", () => ({
  useSearch: () => ({ portfolio: "SOBSTV", basis: "derived_carrying", currency: "KZT" })
}));

const { portfolios, overviewFor, allocationFor, cashFor, issuesFor, readinessFor } = vi.hoisted(() => {
  const portfolios: PortfolioListResponse = {
    items: [
      { code: "SOBSTV", name: "Собственные средства", reporting_currency: "KZT", latest_published_report_date: "2026-07-15", latest_published_snapshot_id: "snap-a" },
      { code: "TABYS", name: "TABYS", reporting_currency: "KZT", latest_published_report_date: "2026-07-15", latest_published_snapshot_id: "snap-b" }
    ],
    combined_report_dates: ["2026-07-15"],
    report_date_mismatch: false
  };

  function overviewFor(snapshotId: string, portfolio: string, purchase: string): SnapshotOverview {
    return {
      id: snapshotId,
      import_id: `import-${snapshotId}`,
      portfolio,
      report_date: "2026-07-15",
      version: 1,
      status: "published",
      data_label: "operational/derived",
      value_label: "Расчётная балансовая стоимость",
      excluded_lot_count: 0,
      excluded_purchase_value_kzt: null,
      metrics: {
        position_count: { basis: "source", value: 10 },
        unique_isin_count: { basis: "source", value: 8 },
        purchase_amount_kzt: { basis: "source", value: purchase },
        derived_carrying_value_kzt: { basis: "derived", value: purchase },
        cash_kzt: { basis: "source", value: "1000" },
        derived_operational_total_kzt: { basis: "derived", value: purchase },
        total_fees_kzt: { basis: "source", value: "10" },
        total_reserves_kzt: { basis: "source", value: "5" },
        official_nav_kzt: { basis: "unavailable", value: null },
        official_performance: { basis: "unavailable", value: null }
      }
    };
  }

  function allocationFor(): AllocationResponse {
    return {
      snapshot_id: "snap-a",
      dimension: "asset_class",
      value_basis: "derived_carrying_value_kzt",
      total_value_kzt: "1000000",
      items: [{ label: "Corporate bond", value_kzt: "1000000", weight_percent: "100", lot_count: 3, instrument_count: 2 }],
      excluded_value_kzt: null,
      excluded_lot_count: 0
    };
  }

  function cashFor(): CashResponse {
    return {
      snapshot_id: "snap-a",
      items: [{ id: "cash-1", raw_label: "ОСТАТОК ДЕНЕЖНЫХ СРЕДСТВ В KZT", currency: "KZT", custodian: null, native_amount: "1000", kzt_amount: "1000", active: true, source: { workbook_name: "test.xls", sheet_name: "ОСИП_ПОРТФЕЛЬ", row_number: 5, parser_version: "test", source_row_id: "row-1", source_kind: "row" } }]
    };
  }

  function issuesFor(): IssuesResponse {
    return { snapshot_id: "snap-a", items: [{ id: "issue-1", code: "DQ-04", severity: "high", message: "Test finding", affected_fields: [], source_refs: [], acknowledgement: null, owner_id: null, due_date: null, is_overdue: false }] };
  }

  function readinessFor(snapshotId: string, portfolio: string): ReportReadiness {
    return {
      snapshot_id: snapshotId,
      portfolio,
      report_date: "2026-07-15",
      version: 1,
      status: "published",
      source: { filename: "test.xls", sha256: "0".repeat(64), parser_version: "test" },
      gates: { independent_approval: true, critical_dq_acknowledged: true, published: true, source_first_mode: true },
      critical_dq_count: 1,
      unacknowledged_critical_count: 0,
      import_id: `import-${snapshotId}`,
      operational_snapshot_export: { ready: true, label: "Готово", blocking_reasons: [] },
      official_report_export: { ready: false, label: "Недоступно", blocking_reasons: ["Официальный NAV недоступен"] }
    };
  }

  return { portfolios, overviewFor, allocationFor, cashFor, issuesFor, readinessFor };
});

vi.mock("../api/client", () => ({
  dashboardApi: {
    portfolios: vi.fn().mockResolvedValue(portfolios),
    overview: vi.fn().mockImplementation((id: string) =>
      Promise.resolve(id === "snap-a" ? overviewFor("snap-a", "SOBSTV", "1000000") : overviewFor("snap-b", "TABYS", "2000000"))
    ),
    allocation: vi.fn().mockResolvedValue(allocationFor()),
    cash: vi.fn().mockResolvedValue(cashFor()),
    issues: vi.fn().mockResolvedValue(issuesFor()),
    readiness: vi.fn().mockImplementation((id: string) =>
      Promise.resolve(id === "snap-a" ? readinessFor("snap-a", "SOBSTV") : readinessFor("snap-b", "TABYS"))
    )
  }
}));

import { LanguageProvider } from "../i18n";
import { ComparisonPage } from "./ComparisonPage";

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <ComparisonPage />
      </LanguageProvider>
    </QueryClientProvider>
  );
}

describe("ComparisonPage", () => {
  it("renders both portfolios' KPI rows once queries resolve", async () => {
    renderPage();
    expect(await screen.findAllByText("SOBSTV", { exact: false })).not.toHaveLength(0);
    expect(await screen.findAllByText("TABYS", { exact: false })).not.toHaveLength(0);
    expect(await screen.findByText("Portfolio comparison")).toBeInTheDocument();
  });

  it("swaps the two portfolio selects", async () => {
    renderPage();
    const selectA = await screen.findByLabelText("Portfolio A") as HTMLSelectElement;
    const selectB = await screen.findByLabelText("Portfolio B") as HTMLSelectElement;
    await screen.findAllByText("SOBSTV", { exact: false });
    expect(selectA.value).toBe("SOBSTV");
    expect(selectB.value).toBe("TABYS");
    fireEvent.click(screen.getByRole("button", { name: "Swap portfolios" }));
    expect(selectA.value).toBe("TABYS");
    expect(selectB.value).toBe("SOBSTV");
  });

  it("shows a warning when the same portfolio is selected for both sides", async () => {
    renderPage();
    const selectB = await screen.findByLabelText("Portfolio B") as HTMLSelectElement;
    fireEvent.change(selectB, { target: { value: "SOBSTV" } });
    expect(await screen.findByText("Choose two different portfolios to compare.")).toBeInTheDocument();
  });
});
