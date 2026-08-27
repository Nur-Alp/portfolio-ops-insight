import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

vi.mock("../api/client", () => ({
  dashboardApi: {
    cash: vi.fn(),
    calendar: vi.fn(),
    provenance: vi.fn(),
    exportCashCalendar: vi.fn()
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
import { CashCalendarPage } from "./CashCalendarPage";

describe("CashCalendarPage", () => {
  it("renders an empty state without crashing when no snapshot is published", async () => {
    await renderWithProviders(<CashCalendarPage />);

    expect(await screen.findByText(/SOBSTV/)).toBeInTheDocument();
  });
});
