import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

vi.mock("../api/client", () => ({
  dashboardApi: {
    overview: vi.fn(),
    allocation: vi.fn(),
    calendar: vi.fn(),
    readiness: vi.fn(),
    provenance: vi.fn()
  }
}));

vi.mock("../hooks/useSelectedSnapshot", () => ({
  useSelectedSnapshot: () => ({
    search: { portfolio: "SOBSTV" },
    portfolios: { isLoading: false, error: null, data: { items: [] } },
    snapshotId: ""
  })
}));

import { renderWithProviders } from "../test/render";
import { OverviewPage } from "./OverviewPage";

describe("OverviewPage", () => {
  it("renders an empty state without crashing when no snapshot is published", async () => {
    await renderWithProviders(<OverviewPage />);

    expect(await screen.findByText(/SOBSTV/)).toBeInTheDocument();
  });
});
