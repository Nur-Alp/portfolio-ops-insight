import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { LanguageProvider } from "../i18n";

// Some components (e.g. KpiCard's BasisBadge) call useSearch()/useMatch(),
// which throw outside a router context. A single root route with no children
// is enough to satisfy that without pulling in the app's full route tree.
// The router's initial match resolves asynchronously even with no loaders,
// so callers must await this before asserting on rendered content.
export async function renderWithProviders(ui: ReactElement): Promise<RenderResult> {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  const rootRoute = createRootRoute({
    component: () => (
      <QueryClientProvider client={client}>
        <LanguageProvider>
          {/* Mirrors AppShell's own portal targets (domain-version-bar-slot,
              topbar-page-control-slot) - DomainPage portals content into
              these by id, so a test rendering DomainPage without the real
              shell needs them present too, or that content silently
              doesn't render at all. */}
          <div id="topbar-page-control-slot" />
          {ui}
          <div id="domain-version-bar-slot" />
        </LanguageProvider>
      </QueryClientProvider>
    )
  });
  const router = createRouter({
    routeTree: rootRoute,
    history: createMemoryHistory({ initialEntries: ["/"] })
  });
  await router.load();
  return render(<RouterProvider router={router} />);
}
