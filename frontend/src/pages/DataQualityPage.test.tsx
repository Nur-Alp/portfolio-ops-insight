import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

vi.mock("../api/client", () => ({
  dashboardApi: {
    issues: vi.fn(),
    metrics: vi.fn(),
    datasetVersions: vi.fn().mockResolvedValue({ items: [] }),
    assignDqIssue: vi.fn(),
    exportDqIssues: vi.fn()
  }
}));

vi.mock("../hooks/useSelectedSnapshot", () => ({
  useSelectedSnapshot: () => ({
    search: { portfolio: "SOBSTV" },
    portfolios: { isLoading: false, error: null, data: { items: [] } },
    snapshotId: "",
    osipEnabled: false
  })
}));

import { renderWithProviders } from "../test/render";
import { DataQualityPage } from "./DataQualityPage";

describe("DataQualityPage", () => {
  it("renders the no-domain-datasets empty state without crashing", async () => {
    await renderWithProviders(<DataQualityPage />);

    expect(await screen.findByText("No datasets are available for this domain yet")).toBeInTheDocument();
  });
});
