import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders as render } from "../../test/render";
import { KpiCard } from "./KpiCard";

describe("KpiCard", () => {
  it("always discloses the metric basis", async () => {
    await render(
      <KpiCard
        label="Расчётная балансовая стоимость"
        value="4 774 363 156 ₸"
        basis="derived"
      />
    );
    expect(screen.getByText("Расчётная балансовая стоимость")).toBeInTheDocument();
    expect(screen.getByText("Derived metric")).toBeInTheDocument();
  });

  it("does not disguise an unavailable metric as zero", async () => {
    await render(<KpiCard label="Официальный NAV" value="Недоступно" basis="unavailable" />);
    expect(screen.getByText("Недоступно", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("Unavailable", { selector: "span" })).toBeInTheDocument();
    expect(screen.queryByText("0 ₸")).not.toBeInTheDocument();
  });
});
