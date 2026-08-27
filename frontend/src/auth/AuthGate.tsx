import { UserManager, WebStorageStateStore, type User } from "oidc-client-ts";
import { type ReactNode, useEffect, useState } from "react";
import { DemoLoginForm } from "./DemoLoginForm";
import { clearDemoSession, isDemoMode, isOidcMode, setDemoSession, setOidcAccessToken, type DemoActor } from "./session";
import { useI18n } from "../i18n";

const DEMO_SESSION_STORAGE_KEY = "portfolio-ops-insight-demo-session";

type StoredDemoSession = { token: string; actor: DemoActor };

function readStoredDemoSession(): StoredDemoSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(DEMO_SESSION_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredDemoSession;
    if (!parsed.token || !parsed.actor) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeStoredDemoSession(session: StoredDemoSession | null): void {
  if (typeof window === "undefined") return;
  if (session) window.sessionStorage.setItem(DEMO_SESSION_STORAGE_KEY, JSON.stringify(session));
  else window.sessionStorage.removeItem(DEMO_SESSION_STORAGE_KEY);
}

let manager: UserManager | null = null;
let initialization: Promise<User> | null = null;

function oidcManager(): UserManager {
  if (manager) return manager;
  const authority = import.meta.env.VITE_OIDC_AUTHORITY;
  const clientId = import.meta.env.VITE_OIDC_CLIENT_ID;
  if (!authority || !clientId) {
    throw new Error("В режиме OIDC требуются VITE_OIDC_AUTHORITY и VITE_OIDC_CLIENT_ID");
  }
  manager = new UserManager({
    authority,
    client_id: clientId,
    redirect_uri: import.meta.env.VITE_OIDC_REDIRECT_URI ?? `${window.location.origin}/auth/callback`,
    post_logout_redirect_uri: window.location.origin,
    response_type: "code",
    scope: import.meta.env.VITE_OIDC_SCOPE ?? "openid profile",
    automaticSilentRenew: true,
    loadUserInfo: false,
    userStore: new WebStorageStateStore({ store: window.sessionStorage })
  });
  return manager;
}

async function initializeSession(): Promise<User> {
  if (initialization) return initialization;
  initialization = (async () => {
    const userManager = oidcManager();
    const callback = window.location.pathname === "/auth/callback";
    const user = callback ? await userManager.signinRedirectCallback() : await userManager.getUser();
    if (callback && user) {
      const returnTo =
        typeof user.state === "object" && user.state && "returnTo" in user.state
          ? String(user.state.returnTo)
          : "/";
      window.history.replaceState({}, document.title, returnTo.startsWith("/") ? returnTo : "/");
    }
    if (!user || user.expired) {
      await userManager.signinRedirect({
        state: { returnTo: `${window.location.pathname}${window.location.search}` }
      });
      return new Promise<User>(() => undefined);
    }
    setOidcAccessToken(user.access_token);
    userManager.events.addUserLoaded((loaded) => setOidcAccessToken(loaded.access_token));
    userManager.events.addUserUnloaded(() => setOidcAccessToken(null));
    userManager.events.addAccessTokenExpired(() => setOidcAccessToken(null));
    return user;
  })();
  return initialization;
}

// Reused by both an expired/invalid token (client.ts's unwrap() dispatches
// this on any 401) and an explicit "log out" click - both cases mean the
// same thing: drop the demo session and show the login form again.
export function triggerDemoSignOut(): void {
  clearDemoSession();
  writeStoredDemoSession(null);
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("osip:unauthorized"));
}

export function AuthGate({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [state, setState] = useState<"loading" | "ready" | "error" | "login">(() => {
    if (isOidcMode()) return "loading";
    if (isDemoMode()) return readStoredDemoSession() ? "ready" : "login";
    return "ready";
  });
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!isOidcMode()) return;
    initializeSession()
      .then(() => setState("ready"))
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : t("auth.oidcUnavailable"));
        setState("error");
      });
  }, [t]);

  useEffect(() => {
    if (!isDemoMode()) return;
    const stored = readStoredDemoSession();
    if (stored) setDemoSession(stored.token, stored.actor);
    const handleUnauthorized = () => setState("login");
    window.addEventListener("osip:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("osip:unauthorized", handleUnauthorized);
  }, []);

  if (state === "loading") {
    return <main className="auth-state"><div className="state-card"><div className="state-card__spinner" /><strong>{t("auth.loading")}</strong><span>{t("auth.loadingDetail")}</span></div></main>;
  }
  if (state === "error") {
    return <main className="auth-state"><div className="state-card state-card--error"><strong>{t("auth.error")}</strong><span>{message}</span></div></main>;
  }
  if (state === "login") {
    return (
      <DemoLoginForm
        onSignedIn={(token, actor) => {
          setDemoSession(token, actor);
          writeStoredDemoSession({ token, actor });
          setState("ready");
        }}
      />
    );
  }
  return children;
}
