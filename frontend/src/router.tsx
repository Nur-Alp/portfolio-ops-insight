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

export const router = createRouter({ routeTree, defaultPreload: "intent" });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
