import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

vi.mock("../api/client", () => ({
  dashboardApi: {
    operationsReadiness: vi.fn().mockResolvedValue({ datasets: [], reconciliations: [], readiness: [] })
  }
}));

import { renderWithProviders } from "../test/render";
import { OperationsPage } from "./OperationsPage";

describe("OperationsPage", () => {
  it("renders the cross-domain readiness register without crashing when there are no datasets yet", async () => {
    await renderWithProviders(<OperationsPage />);

    expect(await screen.findAllByText("0")).not.toHaveLength(0);
  });
});
