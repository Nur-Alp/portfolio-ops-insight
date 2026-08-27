import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

vi.mock("../api/client", () => ({
  dashboardApi: {
    datasetVersions: vi.fn().mockResolvedValue({ items: [] }),
    createSourceUpload: vi.fn(),
    materializeSourceDatasets: vi.fn(),
    approveDataset: vi.fn(),
    publishDataset: vi.fn(),
    rejectDataset: vi.fn(),
    withdrawDataset: vi.fn()
  }
}));

vi.mock("../auth/session", () => ({
  getCurrentDomainScope: () => "risk"
}));

import { renderWithProviders } from "../test/render";
import { ImportsPage } from "./ImportsPage";

describe("ImportsPage", () => {
  it("renders the domain-scoped multi-source upload panel for a non-OSIP domain without crashing", async () => {
    await renderWithProviders(<ImportsPage />);

    expect(await screen.findByText("Choose an .xls or .xlsx workbook")).toBeInTheDocument();
  });
});
