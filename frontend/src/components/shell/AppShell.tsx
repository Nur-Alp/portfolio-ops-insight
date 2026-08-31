import {
  BarChart3,
  BriefcaseBusiness,
  Building2,
  CalendarClock,
  ChevronLeft,
  CircleDollarSign,
  Database,
  Landmark,
  LineChart,
  FileCheck2,
  FileUp,
  LogOut,
  Menu,
  Search,
  ShieldCheck,
  ShieldAlert,
  TableProperties,
  Users,
  X
} from "lucide-react";
import { Link, Outlet, useLocation, useNavigate, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { dashboardApi } from "../../api/client";
import { DOMAIN_OPTIONS, getCurrentDomainScope, getDemoActor, isDemoMode, isOidcMode, setCurrentDomainScope, type DomainScope } from "../../auth/session";
import { triggerDemoSignOut } from "../../auth/AuthGate";
import { formatReportDate } from "../../lib/format";
import { useI18n } from "../../i18n";
import type { DashboardSearch } from "../../router";
import { CommandPalette } from "./CommandPalette";

export const navigation = [
  { to: "/asset-management", labelKey: "nav.assetManagement", icon: LineChart, exact: false, group: "business", domain: "back_office" },
  { to: "/brokerage", labelKey: "nav.brokerage", icon: BriefcaseBusiness, exact: false, group: "business", domain: "client_ops" },
  { to: "/clients", labelKey: "nav.clients", icon: Users, exact: false, group: "business", domain: "client_ops" },
  { to: "/corporate-finance", labelKey: "nav.corporateFinance", icon: Building2, exact: false, group: "business", domain: "corpfin" },
  { to: "/risk", labelKey: "nav.risk", icon: ShieldAlert, exact: false, group: "business", domain: "risk" },

  // The OSIP pages form one working set: overview → positions → cash/events.
  // Keeping them together makes the most-used portfolio workflow discoverable
  // without forcing users to scroll past pending sources.
  { to: "/", labelKey: "nav.overview", icon: BarChart3, exact: true, group: "portfolio", domain: "back_office" },
  { to: "/holdings", labelKey: "nav.holdings", icon: TableProperties, exact: false, group: "portfolio", domain: "back_office" },
  { to: "/cash-calendar", labelKey: "nav.cash", icon: CalendarClock, exact: false, group: "portfolio", domain: "back_office" },

  { to: "/treasury", labelKey: "nav.treasury", icon: Landmark, exact: false, group: "control", domain: "back_office" },
  { to: "/operations", labelKey: "nav.operations", icon: CalendarClock, exact: false, group: "control" },
  { to: "/data-quality", labelKey: "nav.dq", icon: ShieldCheck, exact: false, group: "control" },
  { to: "/imports", labelKey: "nav.imports", icon: FileUp, exact: false, group: "control" },
  { to: "/reporting", labelKey: "nav.reporting", icon: FileCheck2, exact: false, group: "reporting", domain: "back_office" },
  { to: "/accounting", labelKey: "nav.accounting", icon: Database, exact: false, group: "business", domain: "accounting" }
] as const;

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [domainScope, setDomainScope] = useState<DomainScope>(getCurrentDomainScope());
  const { language, setLanguage, t } = useI18n();
  const queryClient = useQueryClient();
  const osipDomainEnabled = domainScope === "*" || domainScope === "back_office";

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);
  const search = useSearch({ strict: false }) as DashboardSearch;
  const portfolios = useQuery({ queryKey: ["portfolios", domainScope], queryFn: dashboardApi.portfolios, enabled: osipDomainEnabled });
  const sessionContext = useQuery({ queryKey: ["session-context"], queryFn: dashboardApi.sessionContext });
  const snapshots = useQuery({
    queryKey: ["snapshots", search.portfolio, "history"],
    queryFn: () => dashboardApi.snapshots(search.portfolio, true),
    enabled: osipDomainEnabled && Boolean(search.portfolio)
  });
  const currentPath = useLocation({ select: (location) => location.pathname });
  const navigate = useNavigate();
  const updateSearch = (patch: Partial<DashboardSearch>) =>
    navigate({ to: currentPath as never, search: { ...search, ...patch } as never, replace: true });
  const changeDomain = (scope: DomainScope) => {
    setCurrentDomainScope(scope);
    setDomainScope(scope);
    void queryClient.invalidateQueries();
    // Only navigate away when the page you're on genuinely doesn't belong to
    // the newly selected domain - domain-agnostic pages (Operations,
    // Data quality, Imports, "All domains") should never be
    // yanked out from under the user just for changing this filter.
    const domainOf = (item: (typeof navigation)[number]): string | undefined =>
      "domain" in item ? item.domain : undefined;
    const currentItem = navigation.find((item) => item.to === currentPath);
    const currentDomain = currentItem ? domainOf(currentItem) : undefined;
    const stillValid = scope === "*" || !currentDomain || currentDomain === scope;
    if (stillValid) return;
    const target = navigation.find((item) => domainOf(item) === scope);
    navigate({ to: (target?.to ?? "/operations") as never, search } as never);
  };
  const portfolioOptions = portfolios.data?.items ?? [
    { code: "SOBSTV", latest_published_report_date: null },
    { code: "TABYS", latest_published_report_date: null }
  ];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t("app.skip")}
      </a>
      <aside className={`sidebar ${menuOpen ? "sidebar--open" : ""}`} aria-label={t("nav.primary")}>
        <div className="brand">
          <span className="brand__mark">F</span>
          <span>
            <strong>Portfolio Operations Insight</strong>
            <small>{t("brand.subtitle")}</small>
          </span>
          <button className="sidebar__mobile-close" type="button" aria-label={t("nav.close")} onClick={() => setMenuOpen(false)}>
            <X aria-hidden="true" />
          </button>
        </div>
        <nav>
          {(["business", "portfolio", "control", "reporting", "pending"] as const).map((group) => {
            const items = navigation.filter((item) => { const domain = "domain" in item ? item.domain : undefined; return item.group === group && (!domain || !sessionContext.data || sessionContext.data.domains.includes("*") || sessionContext.data.domains.includes(domain)); });
            if (!items.length) return null;
            return (
              <div key={group}>
                <p className="nav-group">{t(`nav.group.${group}`)}</p>
                {items.map(({ to, labelKey, icon: Icon, exact }) => (
                  <Link
                    key={to}
                    to={to}
                    search={search}
                    activeOptions={{ exact }}
                    activeProps={{ className: "nav-link nav-link--active" }}
                    inactiveProps={{ className: "nav-link" }}
                    onClick={() => setMenuOpen(false)}
                  >
                    <Icon aria-hidden="true" />
                    {t(labelKey)}
                  </Link>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="sidebar__footer">
          <ChevronLeft aria-hidden="true" />
          {t("nav.controlled")}
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          {/* Domain pages portal a frequently-used, page-specific control here
              (e.g. the accounting quarter/YTD toggle) - unlike the version
              pickers in domain-version-bar-slot below the page content
              (rarely touched, since the default is always the latest
              published data), this leads the persistent header because it's
              actually used on every visit to that page. */}
          <div id="topbar-page-control-slot" className="topbar__page-control" />
          <button className="icon-button topbar__menu" type="button" aria-label={t("nav.open")} onClick={() => setMenuOpen(true)}>
            <Menu aria-hidden="true" />
          </button>
          <button
            type="button"
            className="command-search"
            aria-label={t("top.search")}
            onClick={() => setPaletteOpen(true)}
          >
            <Search aria-hidden="true" />
            <span>{t("top.search")}</span>
            <kbd>⌘K</kbd>
          </button>
          <span className="environment-pill">
            <Database aria-hidden="true" /> {t("top.environment")}
          </span>
          {!isOidcMode() && !isDemoMode() ? <label className="domain-switch">
            <span className="sr-only">{t("top.domain")}</span>
            <select aria-label={t("top.domain")} value={domainScope} onChange={(event) => changeDomain(event.target.value as DomainScope)}>
              {DOMAIN_OPTIONS.map((scope) => <option key={scope} value={scope}>{domainLabel(scope, t)}</option>)}
            </select>
          </label> : null}
          <span className="role-pill">
            {isOidcMode() ? t("top.reader") : isDemoMode() ? (getDemoActor()?.displayName ?? t("top.reader")) : t("top.domainOperator")}
          </span>
          {isDemoMode() ? (
            <button type="button" className="icon-button" aria-label={t("auth.signOut")} title={t("auth.signOut")} onClick={() => triggerDemoSignOut()}>
              <LogOut aria-hidden="true" />
            </button>
          ) : null}
          <div className="language-switch" role="group" aria-label={t("top.language")}>
            {(["ru", "en"] as const).map((option) => (
              <button
                key={option}
                type="button"
                className={`language-switch__option ${language === option ? "language-switch__option--active" : ""}`}
                aria-pressed={language === option}
                onClick={() => setLanguage(option)}
              >
                {option.toUpperCase()}
              </button>
            ))}
          </div>
        </header>

        {osipDomainEnabled && ["/", "/holdings", "/cash-calendar", "/data-quality", "/imports", "/reporting"].includes(currentPath) ? (
        <section className="filterbar" aria-label={t("filter.group")}>
          <label className="filterbar__portfolio">
            <span>{t("filter.portfolio")}</span>
            <select
              value={search.portfolio}
              onChange={(event) =>
                updateSearch({
                  portfolio: event.target.value as DashboardSearch["portfolio"],
                  snapshot: undefined
                })
              }
            >
              {portfolioOptions.map((portfolio) => (
                <option key={portfolio.code} value={portfolio.code}>
                  {portfolio.code} · {formatReportDate(portfolio.latest_published_report_date, language)}
                </option>
              ))}
            </select>
          </label>
          <label className="filterbar__snapshot">
            <span>{t("filter.snapshot")}</span>
            <select
              value={search.snapshot ?? "latest"}
              onChange={(event) => updateSearch({ snapshot: event.target.value === "latest" ? undefined : event.target.value })}
              disabled={snapshots.isLoading || !(snapshots.data?.items.length)}
            >
              <option value="latest">{t("filter.latest")}</option>
              {(snapshots.data?.items ?? []).map((snapshot) => (
                <option key={snapshot.id} value={snapshot.id}>
                  {formatReportDate(snapshot.report_date, language)} · {t("filter.version", { value: snapshot.version })}{snapshot.status === "superseded" ? ` · ${t("filter.superseded")}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t("filter.basis")}</span>
            <select
              value={search.basis}
              onChange={(event) =>
                updateSearch({ basis: event.target.value as DashboardSearch["basis"] })
              }
            >
              <option value="derived_carrying">{t("overview.carrying")}</option>
              <option value="purchase">{t("holding.purchase")}</option>
            </select>
          </label>
          <span className="filterbar__currency-note">{t("filter.currency")}: KZT</span>
          <span className="filterbar__asof">
            <CircleDollarSign aria-hidden="true" /> {t("nav.unavailable")}
          </span>
        </section>
        ) : null}

        <main id="main-content" className="main-content">
          <Outlet />
        </main>

        {/* Multi-source domain pages (Brokerage, Clients, Asset Management,
            Corporate Finance, Accounting, Risk) portal their own version
            control into this slot. Moved below the page content (by
            request) - it's rarely touched day to day since the default is
            always the latest published data, so it no longer needs to sit
            above everything else on every visit. */}
        <div id="domain-version-bar-slot" />

        <footer className="disclosure">
          {t("disclosure")}
        </footer>
      </div>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        domainScope={domainScope}
        actorDomains={sessionContext.data?.domains}
      />
    </div>
  );
}

function domainLabel(scope: DomainScope, t: (key: string, values?: Record<string, string | number | null | undefined>) => string): string {
  const labels: Record<DomainScope, string> = {
    "*": t("top.domain.all"),
    back_office: t("top.domain.backOffice"),
    client_ops: t("top.domain.clientOps"),
    corpfin: t("top.domain.corpfin"),
    accounting: t("top.domain.accounting"),
    risk: t("top.domain.risk")
  };
  return labels[scope];
}
