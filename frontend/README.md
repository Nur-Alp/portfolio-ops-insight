# OSIP dashboard frontend

Maintainable React/TypeScript implementation of the OSIP workbook-only dashboard. It follows the captured Portfolio Operations Insight interaction grammar—dark analytical shell, dense cards/tables, persistent filters, evidence drawers and status semantics—without treating the captured compiled bundles as source code.

```bash
npm install
npm run dev
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`. Copy
`.env.example` to `.env` to override the local development identity or API base.
Production `VITE_AUTH_MODE=oidc` uses authorization code with PKCE, session-scoped
token storage, and bearer API requests. Authority, client ID, redirect URI, and
scope must match the organization IdP registration; OIDC mode cannot emit local
actor/role/portfolio headers.

```bash
npm run build
npm test
npm run api:check
npx playwright install chromium
npm run test:e2e
```

The browser suite starts a disposable SQLite-backed FastAPI service, imports and
publishes both repository workbooks with independent test actors, and exercises
the live UI. It covers every route, accessibility, evidence drawers, idempotent
upload, controlled artifact download, desktop baselines, and the mobile shell.
Refresh reviewed visual baselines deliberately with `npm run test:e2e:update`.
`src/api/schema.d.ts` is generated from `../docs/openapi.json`; do not edit it
directly. Use `npm run api:generate` after regenerating the backend contract.

Current implemented surface:

- responsive application shell and URL-backed portfolio/value-basis/currency filters;
- accessible metric basis badges, status pills, KPI cards, panels, tables, drawers and loading/error/empty states;
- live Portfolio Overview backed by published snapshot, allocation, calendar and report-readiness APIs;
- aggregated Holdings with immutable lot/source drill-down;
- Cash & Calendar with active/template separation and evidence drawers;
- Data Quality with governed metrics, filters, acknowledgements and source evidence;
- Source Imports with upload, prior-approved comparison, independent review and publication controls;
- Reporting readiness with explicit operational versus unavailable official output policy.
- controlled, reproducible CSV report generation and download.
