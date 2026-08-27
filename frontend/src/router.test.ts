import { describe, expect, it } from "vitest";
import { validateDashboardSearch } from "./router";


describe("dashboard URL filters", () => {
  it("retains supported reproducible filters", () => {
    expect(
      validateDashboardSearch({
        portfolio: "TABYS",
        basis: "purchase",
        currency: "native"
      })
    ).toEqual({ portfolio: "TABYS", basis: "purchase", currency: "native" });
  });

  it("retains a newly registered portfolio code while normalizing unsupported bases", () => {
    expect(
      validateDashboardSearch({
        portfolio: "UNKNOWN",
        basis: "market_value",
        currency: "USD"
      })
    ).toEqual({
      portfolio: "UNKNOWN",
      basis: "derived_carrying",
      currency: "KZT"
    });
  });
});
