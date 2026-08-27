export type DevelopmentIdentity = { actorId: string; roles: string; portfolios?: string; domains?: string };

export type DemoActor = {
  actorId: string;
  username: string;
  displayName: string;
  roles: string[];
  domains: string[];
  portfolios: string[];
};

export const DOMAIN_OPTIONS = ["*", "back_office", "client_ops", "corpfin", "accounting", "risk"] as const;
export type DomainScope = typeof DOMAIN_OPTIONS[number];
const DOMAIN_STORAGE_KEY = "portfolio-ops-insight-domain-scope";

const authMode = import.meta.env.VITE_AUTH_MODE ?? "development";
let oidcAccessToken: string | null = null;
let demoAccessToken: string | null = null;
let demoActor: DemoActor | null = null;

export function isOidcMode(): boolean {
  return authMode === "oidc";
}

export function isDemoMode(): boolean {
  return authMode === "demo";
}

export function setOidcAccessToken(token: string | null): void {
  oidcAccessToken = token;
}

export function setDemoSession(token: string, actor: DemoActor): void {
  demoAccessToken = token;
  demoActor = actor;
}

export function clearDemoSession(): void {
  demoAccessToken = null;
  demoActor = null;
}

export function getDemoActor(): DemoActor | null {
  return demoActor;
}

export function getCurrentDomainScope(): DomainScope {
  // A local launcher can pin one operator to one domain without changing the
  // API identity headers. The broader actor-domain setting remains the
  // fallback for multi-domain supervisors and tests.
  const fallback = (import.meta.env.VITE_DOMAIN_SCOPE ?? import.meta.env.VITE_ACTOR_DOMAINS ?? "*").trim();
  if (typeof window === "undefined") return isDomainScope(fallback) ? fallback : "*";
  // localStorage, not sessionStorage: this is the local per-machine
  // dashboard, and the chosen domain should still be there the next time
  // this operator opens it, not just for as long as the browser tab stays
  // open.
  const stored = window.localStorage.getItem(DOMAIN_STORAGE_KEY);
  return isDomainScope(stored ?? "") ? (stored as DomainScope) : isDomainScope(fallback) ? fallback : "*";
}

export function setCurrentDomainScope(scope: DomainScope): void {
  if (typeof window !== "undefined") window.localStorage.setItem(DOMAIN_STORAGE_KEY, scope);
}

export function authorizationHeaders(identity?: DevelopmentIdentity): Record<string, string> {
  if (isOidcMode()) {
    if (!oidcAccessToken) throw new Error("Сеанс OIDC ещё не готов");
    return { Authorization: `Bearer ${oidcAccessToken}` };
  }
  if (isDemoMode()) {
    if (!demoAccessToken) throw new Error("Демо-сессия ещё не готова");
    return { Authorization: `Bearer ${demoAccessToken}` };
  }
  // Local (non-OIDC, non-demo) mode simulates exactly one person per domain
  // doing the whole workflow themselves - upload, review, publish, and read
  // (README "Local domain operator": "one responsible operator per domain").
  // A single identity for every call is what makes that true: an operator's
  // own upload must be visible to their own very next read, since dataset
  // visibility is scoped strictly by actor id (docs/domain-upload-instructions.md
  // "Visibility rule"). Previously reads defaulted to "dashboard-reader"
  // while upload/review/publish actions were hardcoded to "local-uploader"/
  // "local-reviewer"/"local-publisher" - four different identities that
  // never saw each other's work, so the upload confirmation banner on
  // ImportsPage could never appear for a fresh local setup. That
  // fragmentation still lingers in a long-running local database as
  // datasets uploaded under those old identities (and "phase2-verify" from
  // earlier test runs) - "admin" in the default role list is the
  // cross-uploader bypass (_actor_can_read_uploader_id in
  // routes/multi_source.py) that lets the one real local operator see all
  // of their own historical uploads regardless of which identity happened
  // to create them. identity_provider="development" (this whole code path)
  // is refused outright in production, so this default never reaches a
  // real multi-operator deployment.
  return {
    "X-Actor-Id": identity?.actorId ?? import.meta.env.VITE_ACTOR_ID ?? "local-operator",
    "X-Actor-Roles":
      identity?.roles ?? import.meta.env.VITE_ACTOR_ROLES ?? "admin,uploader,reviewer,publisher,reader",
    "X-Actor-Portfolios":
      identity?.portfolios ?? import.meta.env.VITE_ACTOR_PORTFOLIOS ?? "*",
    "X-Actor-Domains":
      identity?.domains ?? getCurrentDomainScope()
  };
}

function isDomainScope(value: string): value is DomainScope {
  return (DOMAIN_OPTIONS as readonly string[]).includes(value);
}
