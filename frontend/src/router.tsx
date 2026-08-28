import {
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
  redirect
} from "@tanstack/react-router";
import { AppShell } from "./components/shell/AppShell";

// Route components are code-split per page (rather than imported eagerly)
// so the initial bundle only pays for the shell and whichever page the
// user actually lands on; TanStack Router preloads the target chunk on
// link hover/focus via defaultPreload: "intent" below.
const OverviewPage = lazyRouteComponent(() => import("./pages/OverviewPage"), "OverviewPage");
const HoldingsPage = lazyRouteComponent(() => import("./pages/HoldingsPage"), "HoldingsPage");
const CashCalendarPage = lazyRouteComponent(() => import("./pages/CashCalendarPage"), "CashCalendarPage");
const DataQualityPage = lazyRouteComponent(() => import("./pages/DataQualityPage"), "DataQualityPage");
const ImportsPage = lazyRouteComponent(() => import("./pages/ImportsPage"), "ImportsPage");
const ReportingPage = lazyRouteComponent(() => import("./pages/ReportingPage"), "ReportingPage");
const ComparisonPage = lazyRouteComponent(() => import("./pages/ComparisonPage"), "ComparisonPage");
const DomainPage = lazyRouteComponent(() => import("./pages/DomainPage"), "DomainPage");
const OperationsPage = lazyRouteComponent(() => import("./pages/OperationsPage"), "OperationsPage");

export interface DashboardSearch {
  portfolio: string;
  snapshot?: string;
  basis: "derived_carrying" | "purchase";
  currency: "KZT" | "native";
  term?: string;
}

function allowed<T extends string>(
  value: unknown,
  values: readonly T[],
  fallback: T
): T {
  return typeof value === "string" && values.includes(value as T)
    ? (value as T)
    : fallback;
}

const rootRoute = createRootRoute({
  validateSearch: validateDashboardSearch,
  component: AppShell
});

export function validateDashboardSearch(
  search: Record<string, unknown>
): DashboardSearch {
  return {
    portfolio: typeof search.portfolio === "string" && search.portfolio.trim()
      ? search.portfolio.trim().toUpperCase()
      : "SOBSTV",
    snapshot: typeof search.snapshot === "string" && search.snapshot.trim()
      ? search.snapshot.trim()
      : undefined,
    basis: allowed(search.basis, ["derived_carrying", "purchase"], "derived_carrying"),
    currency: allowed(search.currency, ["KZT", "native"], "KZT"),
    term: typeof search.term === "string" && search.term.trim()
      ? search.term.trim()
      : undefined
  };
}

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: OverviewPage
});

const holdingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/holdings",
  component: HoldingsPage
});
const cashRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/cash-calendar",
  component: CashCalendarPage
});
const qualityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/data-quality",
  component: DataQualityPage
});
const importsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/imports",
  component: ImportsPage
});
const reportingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reporting",
  component: ReportingPage
});
const comparisonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/comparison",
  component: ComparisonPage
});

const corporateFinanceRoute = createRoute({ getParentRoute: () => rootRoute, path: "/corporate-finance", component: () => <DomainPage kind="corporate-finance" /> });
const brokerageRoute = createRoute({ getParentRoute: () => rootRoute, path: "/brokerage", component: () => <DomainPage kind="brokerage" /> });
const clientsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/clients", component: () => <DomainPage kind="clients" /> });
const assetManagementRoute = createRoute({ getParentRoute: () => rootRoute, path: "/asset-management", component: () => <DomainPage kind="asset-management" /> });
const treasuryRoute = createRoute({ getParentRoute: () => rootRoute, path: "/treasury", component: () => <DomainPage kind="treasury" /> });
const accountingRoute = createRoute({ getParentRoute: () => rootRoute, path: "/accounting", component: () => <DomainPage kind="accounting" /> });
const riskRoute = createRoute({ getParentRoute: () => rootRoute, path: "/risk", component: () => <DomainPage kind="risk" /> });
const operationsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/operations", component: OperationsPage });
const myWorkRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/my-work",
  beforeLoad: ({ search }) => {
    throw redirect({ to: "/operations", search });
  }
});

const routeTree = rootRoute.addChildren([
  overviewRoute,
  holdingsRoute,
  cashRoute,
  qualityRoute,
  importsRoute,
  reportingRoute,
  comparisonRoute,
  corporateFinanceRoute,
  brokerageRoute,
  clientsRoute,
  assetManagementRoute,
  treasuryRoute,
  operationsRoute,
  myWorkRoute,
  accountingRoute,
  riskRoute
]);

// scripts/launch.py always opens a fresh browser tab at the bare root URL
// (plus a cache-busting ?build= param) after every restart, which otherwise
// bounces the user back to the Overview page no matter which domain they had
// open. Resume the last page instead: on a hard page load that lands on "/"
// with nothing else to distinguish it (no deep-linked search params beyond
// the launcher's own ?build=), rewrite the URL to the last route recorded
// below before the router reads window.location for its initial state. This
// only runs once per hard load (module-level, evaluated on import) - an
// in-app click on the "Overview" nav link is a client-side navigation that
// never re-imports this module, so it is never hijacked.
export const LAST_ROUTE_STORAGE_KEY = "osip:last-route";

export function resumeLastRouteOnBoot(): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname !== "/") return;
  const bootstrapSearch = new URLSearchParams(window.location.search);
  bootstrapSearch.delete("build");
  if ([...bootstrapSearch.keys()].length > 0) return; // a real deep link to "/", not the launcher's bare URL
  try {
    const lastRoute = window.localStorage.getItem(LAST_ROUTE_STORAGE_KEY);
    if (lastRoute && lastRoute.startsWith("/") && lastRoute !== "/") {
      window.history.replaceState(null, "", lastRoute);
    }
  } catch {
    // Storage can throw in a locked-down browser context - resuming the
    // last route is a convenience, never worth failing the app boot over.
  }
}
resumeLastRouteOnBoot();

export const router = createRouter({ routeTree, defaultPreload: "intent" });

router.subscribe("onResolved", () => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LAST_ROUTE_STORAGE_KEY, window.location.pathname + window.location.search);
  } catch {
    // Same reasoning as above - never let this block navigation.
  }
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
