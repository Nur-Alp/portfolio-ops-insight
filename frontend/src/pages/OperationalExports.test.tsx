import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  cash: vi.fn().mockResolvedValue({ snapshot_id: "snapshot-1", items: [{ id: "cash-1", raw_label: "KZT", currency: "KZT", custodian: "Кастодиан", native_amount: "10", kzt_amount: "10", active: true, source: { row_number: 1 } }] }),
  calendar: vi.fn().mockResolvedValue({ snapshot_id: "snapshot-1", counts: { upcoming: 0, overdue_settlements: 0 }, items: [] }),
  issues: vi.fn().mockResolvedValue({ snapshot_id: "snapshot-1", items: [] }),
  metrics: vi.fn().mockResolvedValue({ items: [] }),
  imports: vi.fn().mockResolvedValue({ items: [] }),
  datasetVersions: vi.fn().mockResolvedValue({ items: [] }),
  provenance: vi.fn().mockResolvedValue({
    snapshot_id: "snapshot-1",
    portfolio: "SOBSTV",
    report_date: "2026-07-15",
    version: 1,
    source_filename: "test.xls",
    metrics: {}
  }),
  exportCashCalendar: vi.fn().mockResolvedValue(undefined),
  exportDqIssues: vi.fn().mockResolvedValue(undefined),
  exportImportRegistry: vi.fn().mockResolvedValue(undefined),
  assignDqIssue: vi.fn(), upload: vi.fn(), comparison: vi.fn(), approve: vi.fn(), publish: vi.fn(), withdraw: vi.fn(),
  approveDataset: vi.fn(), publishDataset: vi.fn(), rejectDataset: vi.fn(), withdrawDataset: vi.fn(), datasetMapping: vi.fn(), confirmDatasetMapping: vi.fn()
}));

vi.mock("../api/client", () => ({ dashboardApi: api }));
vi.mock("../hooks/useSelectedSnapshot", () => ({
  useSelectedSnapshot: () => ({
    search: { portfolio: "SOBSTV", basis: "derived_carrying", currency: "KZT" },
    portfolios: { isLoading: false, data: { items: [] } },
    portfolio: { code: "SOBSTV" }, snapshotId: "snapshot-1", osipEnabled: true
  })
}));

import { LanguageProvider } from "../i18n";
import { CashCalendarPage } from "./CashCalendarPage";
import { DataQualityPage } from "./DataQualityPage";
import { ImportsPage, MultiSourceUploadPanel } from "./ImportsPage";

function renderPage(page: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>{page}</LanguageProvider>
    </QueryClientProvider>
  );
}

afterEach(() => cleanup());

describe("operational Excel exports", () => {
  it("sends the visible cash-template setting", async () => {
    renderPage(<CashCalendarPage />);
    // The cash-and-calendar export produces one combined workbook, so both
    // the "Cash by custodian" and "Event calendar" panels offer the same
    // "Export to Excel" action as a convenience entry point.
    const [exportButton] = await screen.findAllByRole("button", { name: "Export to Excel" });
    fireEvent.click(exportButton);
    await waitFor(() => expect(api.exportCashCalendar).toHaveBeenCalledWith("snapshot-1", false));
  });

  it("sends the active DQ search and severity filters", async () => {
    renderPage(<DataQualityPage />);
    await screen.findByText("Data-quality checks");
    fireEvent.change(screen.getByPlaceholderText("Code, rule, field"), { target: { value: "DQ-04" } });
    fireEvent.change(screen.getByLabelText("Severity filter"), { target: { value: "high" } });
    fireEvent.click(screen.getByRole("button", { name: "Export to Excel" }));
    await waitFor(() => expect(api.exportDqIssues).toHaveBeenCalledWith("snapshot-1", { term: "DQ-04", severity: "high" }));
  });

  it("exports the registry visible to the current reader", async () => {
    renderPage(<ImportsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Export to Excel" }));
    await waitFor(() => expect(api.exportImportRegistry).toHaveBeenCalledTimes(1));
  });

  it("does not mutate a dataset when a native reason prompt is cancelled", async () => {
    api.datasetVersions.mockResolvedValue({ items: [{
      id: "dataset-1", dataset_type: "corporate_finance", scope_code: "CORPFIN", business_date: "2026-07-01", version: 1,
      source_filename: "corporate.xlsx", status: "validated", issues: [], summary: {}
    }] });
    const prompt = vi.spyOn(window, "prompt").mockReturnValue(null);
    renderPage(<MultiSourceUploadPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
    expect(prompt).toHaveBeenCalledWith("Rejection reason");
    expect(api.rejectDataset).not.toHaveBeenCalled();
    prompt.mockRestore();
  });

  it("uses the reason returned by the native prompt for reject and withdraw actions", async () => {
    api.datasetVersions.mockResolvedValue({ items: [{
      id: "validated-1", dataset_type: "corporate_finance", scope_code: "CORPFIN", business_date: "2026-07-01", version: 1,
      source_filename: "corporate.xlsx", status: "validated", issues: [], summary: {}
    }, {
      id: "published-1", dataset_type: "fund_unit_history", scope_code: "TABYS", business_date: "2026-07-01", version: 1,
      source_filename: "fund.xlsx", status: "published", issues: [], summary: {}
    }] });
    const prompt = vi.spyOn(window, "prompt").mockReturnValueOnce("Incorrect source").mockReturnValueOnce("Superseded version");
    renderPage(<MultiSourceUploadPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
    await waitFor(() => expect(api.rejectDataset).toHaveBeenCalledWith("validated-1", "Incorrect source"));
    fireEvent.click(screen.getByRole("button", { name: "Withdraw" }));
    await waitFor(() => expect(api.withdrawDataset).toHaveBeenCalledWith("published-1", "Superseded version"));
    prompt.mockRestore();
  });
});
