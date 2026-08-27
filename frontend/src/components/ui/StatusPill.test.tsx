import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../../test/render";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it("distinguishes a source-date mismatch from a failed reconciliation", async () => {
    await renderWithProviders(<StatusPill status="date_mismatch" />);
    const pill = screen.getByText("Date mismatch");
    expect(pill).toHaveClass("status-pill--warning");
    expect(pill).not.toHaveTextContent("Failed");
  });
});
