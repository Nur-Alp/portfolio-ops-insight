import { afterEach, describe, expect, it, vi } from "vitest";


afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
  window.sessionStorage.clear();
  window.localStorage.clear();
});

describe("authorization headers", () => {
  it("uses explicit development identity and portfolio headers locally", async () => {
    vi.stubEnv("VITE_AUTH_MODE", "development");
    const { authorizationHeaders } = await import("./session");
    expect(
      authorizationHeaders({ actorId: "reviewer-1", roles: "reviewer", portfolios: "SOBSTV" })
    ).toEqual({
      "X-Actor-Id": "reviewer-1",
      "X-Actor-Roles": "reviewer",
      "X-Actor-Portfolios": "SOBSTV",
      "X-Actor-Domains": "*"
    });
  });

  it("never emits impersonation headers in OIDC mode", async () => {
    vi.stubEnv("VITE_AUTH_MODE", "oidc");
    const { authorizationHeaders, setOidcAccessToken } = await import("./session");
    expect(() => authorizationHeaders()).toThrow("Сеанс OIDC ещё не готов");
    setOidcAccessToken("signed-access-token");
    expect(
      authorizationHeaders({ actorId: "forged", roles: "publisher", portfolios: "*" })
    ).toEqual({ Authorization: "Bearer signed-access-token" });
  });

  it("never emits impersonation headers in demo mode", async () => {
    vi.stubEnv("VITE_AUTH_MODE", "demo");
    const { authorizationHeaders, setDemoSession, isDemoMode } = await import("./session");
    expect(isDemoMode()).toBe(true);
    expect(() => authorizationHeaders()).toThrow("Демо-сессия ещё не готова");
    setDemoSession("demo-token", {
      actorId: "demo-risk",
      username: "risk",
      displayName: "Демо: Риски",
      roles: ["reader"],
      domains: ["risk"],
      portfolios: ["*"]
    });
    expect(
      authorizationHeaders({ actorId: "forged", roles: "publisher", portfolios: "*" })
    ).toEqual({ Authorization: "Bearer demo-token" });
  });

  it("clears the demo session and actor on sign-out", async () => {
    vi.stubEnv("VITE_AUTH_MODE", "demo");
    const { authorizationHeaders, setDemoSession, clearDemoSession, getDemoActor } = await import("./session");
    setDemoSession("demo-token", {
      actorId: "demo-risk",
      username: "risk",
      displayName: "Демо: Риски",
      roles: ["reader"],
      domains: ["risk"],
      portfolios: ["*"]
    });
    expect(getDemoActor()?.username).toBe("risk");
    clearDemoSession();
    expect(getDemoActor()).toBeNull();
    expect(() => authorizationHeaders()).toThrow("Демо-сессия ещё не готова");
  });

  it("persists a selected domain across restarts, not just the browser session", async () => {
    vi.stubEnv("VITE_AUTH_MODE", "development");
    const { getCurrentDomainScope, setCurrentDomainScope, authorizationHeaders } = await import("./session");
    expect(getCurrentDomainScope()).toBe("*");
    setCurrentDomainScope("back_office");
    expect(getCurrentDomainScope()).toBe("back_office");
    expect(authorizationHeaders()["X-Actor-Domains"]).toBe("back_office");
    // localStorage, not sessionStorage: it must still be there after the
    // tab/browser closes and reopens, which is exactly what sessionStorage
    // does not survive.
    expect(window.localStorage.getItem("portfolio-ops-insight-domain-scope")).toBe("back_office");
    expect(window.sessionStorage.getItem("portfolio-ops-insight-domain-scope")).toBeNull();
  });
});
