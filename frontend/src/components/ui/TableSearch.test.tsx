import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Panel } from "./Panel";
import { TableSearch } from "./TableSearch";

describe("TableSearch", () => {
  it("filters rows within its containing panel", async () => {
    render(
      <Panel title="Records" action={<TableSearch label="Search records" placeholder="Search records" />}>
        <table><tbody><tr><td>Alpha</td></tr><tr><td>Beta</td></tr></tbody></table>
      </Panel>
    );

    const rows = screen.getAllByRole("row");
    fireEvent.change(screen.getByPlaceholderText("Search records"), { target: { value: "beta" } });
    await waitFor(() => {
      expect(rows[0]).toHaveClass("table-row--search-hidden");
      expect(rows[1]).not.toHaveClass("table-row--search-hidden");
    });
  });
});
