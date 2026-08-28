import { afterEach, describe, expect, it } from "vitest";
import { LAST_ROUTE_STORAGE_KEY, resumeLastRouteOnBoot, validateDashboardSearch } from "./router";

function setLocation(pathname: string, search = "") {
  window.history.replaceState(null, "", pathname + search);
}


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

describe("resumeLastRouteOnBoot", () => {
  afterEach(() => {
    window.localStorage.removeItem(LAST_ROUTE_STORAGE_KEY);
    setLocation("/");
  });

  it("rewrites the launcher's bare root URL to the last visited route", () => {
    window.localStorage.setItem(LAST_ROUTE_STORAGE_KEY, "/accounting");
    setLocation("/", "?build=abc123");
    resumeLastRouteOnBoot();
    expect(window.location.pathname).toBe("/accounting");
  });

  it("does nothing when there is no recorded last route", () => {
    setLocation("/", "?build=abc123");
    resumeLastRouteOnBoot();
    expect(window.location.pathname).toBe("/");
  });

  it("leaves a real deep link to root untouched", () => {
    window.localStorage.setItem(LAST_ROUTE_STORAGE_KEY, "/accounting");
    setLocation("/", "?portfolio=TABYS");
    resumeLastRouteOnBoot();
    expect(window.location.pathname + window.location.search).toBe("/?portfolio=TABYS");
  });

  it("leaves a non-root page untouched", () => {
    window.localStorage.setItem(LAST_ROUTE_STORAGE_KEY, "/accounting");
    setLocation("/risk");
    resumeLastRouteOnBoot();
    expect(window.location.pathname).toBe("/risk");
  });
});
