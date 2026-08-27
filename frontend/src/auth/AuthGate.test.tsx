import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const demoLogin = vi.fn();
vi.mock("../api/client", () => ({
  dashboardApi: { demoLogin: (...args: unknown[]) => demoLogin(...args) }
}));

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.resetModules();
  vi.clearAllMocks();
  window.sessionStorage.clear();
});

describe("AuthGate in demo mode", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_AUTH_MODE", "demo");
  });

  it("shows a login form, then the app after a successful sign-in", async () => {
    demoLogin.mockResolvedValue({
      access_token: "demo-token",
      token_type: "bearer",
      expires_at: "2026-01-01T00:00:00Z",
      actor: {
        actor_id: "demo-risk",
        username: "risk",
        display_name: "Демо: Риски",
        roles: ["reader"],
        domains: ["risk"],
        portfolios: ["*"]
      }
    });

    const { LanguageProvider } = await import("../i18n");
    const { AuthGate } = await import("./AuthGate");
    render(
      <LanguageProvider>
        <AuthGate>
          <div>Protected content</div>
        </AuthGate>
      </LanguageProvider>
    );

    expect(await screen.findByLabelText("Username")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "risk" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "hunter2pass" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Protected content")).toBeInTheDocument();
    expect(demoLogin).toHaveBeenCalledWith("risk", "hunter2pass");
    expect(window.sessionStorage.getItem("portfolio-ops-insight-demo-session")).toContain("demo-token");
  });

  it("shows the server's error message on a failed login attempt", async () => {
    demoLogin.mockRejectedValue(new Error("Неверное имя пользователя или пароль"));

    const { LanguageProvider } = await import("../i18n");
    const { AuthGate } = await import("./AuthGate");
    render(
      <LanguageProvider>
        <AuthGate>
          <div>Protected content</div>
        </AuthGate>
      </LanguageProvider>
    );

    fireEvent.change(await screen.findByLabelText("Username"), { target: { value: "risk" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Неверное имя пользователя или пароль")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("hydrates an existing session from storage without re-prompting", async () => {
    window.sessionStorage.setItem(
      "portfolio-ops-insight-demo-session",
      JSON.stringify({
        token: "stored-token",
        actor: {
          actorId: "demo-risk",
          username: "risk",
          displayName: "Демо: Риски",
          roles: ["reader"],
          domains: ["risk"],
          portfolios: ["*"]
        }
      })
    );

    const { LanguageProvider } = await import("../i18n");
    const { AuthGate } = await import("./AuthGate");
    render(
      <LanguageProvider>
        <AuthGate>
          <div>Protected content</div>
        </AuthGate>
      </LanguageProvider>
    );

    expect(await screen.findByText("Protected content")).toBeInTheDocument();
    expect(demoLogin).not.toHaveBeenCalled();
  });

  it("returns to the login form when a 401 is dispatched (expired/invalid token) or on explicit sign-out", async () => {
    window.sessionStorage.setItem(
      "portfolio-ops-insight-demo-session",
      JSON.stringify({
        token: "stored-token",
        actor: {
          actorId: "demo-risk",
          username: "risk",
          displayName: "Демо: Риски",
          roles: ["reader"],
          domains: ["risk"],
          portfolios: ["*"]
        }
      })
    );

    const { LanguageProvider } = await import("../i18n");
    const { AuthGate, triggerDemoSignOut } = await import("./AuthGate");
    render(
      <LanguageProvider>
        <AuthGate>
          <div>Protected content</div>
        </AuthGate>
      </LanguageProvider>
    );
    expect(await screen.findByText("Protected content")).toBeInTheDocument();

    triggerDemoSignOut();

    await waitFor(() => expect(screen.getByLabelText("Username")).toBeInTheDocument());
    expect(window.sessionStorage.getItem("portfolio-ops-insight-demo-session")).toBeNull();
  });
});
