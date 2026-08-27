# Portfolio Operations Insight — feature inventory

> **Maintenance note:** this file is a living inventory of everything actually
> implemented in the app, kept current as work lands. **Whenever a feature is
> added, changed, or removed, update the relevant section below in the same
> change.** Don't let this drift the way `docs/functionality-breakdown.md`
> (an earlier, narrower snapshot) did — if a feature here no longer matches
> the code, fix the entry rather than leaving it stale. For what's still
> missing versus the Portfolio Operations Insight reference product, see
> `docs/product-feature-gap-register.md`.

## 1. Workbook ingestion & parsing

- Global physical-workbook registry (`source_uploads`) deduplicates immutable blobs by SHA-256 while scoping ownership records by uploader, so the same approved bytes can be re-uploaded into another operator's private workspace without copying or changing the source blob. It detects supported feeds from workbook structure and stable headers, never from filenames. Lock files, `desktop.ini`, empty files and invalid signatures are rejected before child creation.
- One physical workbook can produce independently governed dataset children with dataset/scope/source/business dates and separate validation, approval, publication, supersession, rejection and withdrawal.
- Implemented adapters: TABYS valuation and partitions, SAQ/TABYS unit history, client/brokerage canonical partitions, corporate-finance register, and accounting landing/DQ evidence.
- Generic dataset records preserve normalized payload, immutable raw values, formulas, cached values, and workbook/sheet/row provenance separately.
- Tolerant `.xls` parser for the legacy OSIP export (`backend/osip_dashboard/ingestion/osip_workbook.py`): finds the header by stable column labels rather than fixed row numbers, so inserted/reordered rows don't break it; a changed/renamed column is a hard schema-contract failure.
- Content-based row classification into current position lots, settlement events, and cash balances; the OSIP "Предстоящие расчеты" (upcoming settlements) section is deliberately excluded from import, calendar, totals, and DQ checks.
- Exact settlement deduplication (e.g. 10 raw SOBSTV rows → 5 records) without discarding either original source row reference (DQ-02 finding recorded).
- Broken-calculated-field detection (`BROKEN_CALCULATED_FIELDS`): workbook columns known to cache stale/blank formula results are treated as genuinely unavailable (DQ-01 blocker) rather than silently defaulting to zero, unless a real formula is present in the underlying BIFF stream.
- `current_ytm` is read as-is from the source workbook (column 25) — a `source`-basis field, not calculated.
- Derived carrying value = `AA × AU × AT + AR` (native carrying value × FX rate × principal indexation + accrued income), computed independently rather than trusting the workbook's own (unreliable) KZT/market-value columns — explicitly labeled `operational/derived`, never official NAV or market value.
- HPR (holding period return) computed at instrument-aggregation level: `(derived_carrying_value_kzt − purchase_amount_kzt + received_dividends_kzt + estimated_paid_coupon_income_kzt) × 100 / purchase_amount_kzt`. Received dividends come from the supplied local `sources/dividends.xlsx` history (override with `OSIP_DIVIDENDS_FILE`) when `ex_date > purchase_date` and `pay_date < current_date`; standalone `US` ticker tokens are reduced by 15% withholding tax. Coupon-bearing lots add a gross approximation `nominal × quantity × coupon_rate × holding_days / 360` less the current accrued coupon already in carrying value; this is explicitly an estimate rather than a paid-coupon ledger.
- Immutable, SHA-256-addressed original file storage (`BlobStore` / `LocalBlobStore`), independent of parsed data.
- Golden regression tests against both real supplied workbooks (SOBSTV, TABYS).

## 2. Import & publication workflow

- Multi-source wizard detects partitions, allows explicit scope confirmation, creates each selected child independently and retains failed parsing attempts as evidence.
- Generic child idempotency is scoped by source upload + dataset type + scope; rejected/failed/withdrawn children can be recreated. Publishing supersedes only the same dataset type/scope/business date.
- Upload requires an explicit portfolio code (workbooks carry no reliable portfolio identifier); a new code creates a portfolio record, an existing code is reused.
- Idempotent re-upload: identical bytes to the same portfolio return the existing import rather than duplicating it, scoped to *active* assignments only — `rejected`/`failed`/`withdrawn` imports don't block a fresh retry of the same bytes.
- Workflow states: `draft → validating → validated → approved → published`, plus terminal `failed`, `rejected`, `superseded`, `withdrawn`.
- Four-eyes approval is retained for controlled/hosted OSIP workflows. In the
  local `OSIP_SOURCE_FIRST_MODE` deployment, a structurally valid OSIP source
  is published automatically; blocker/high findings remain source evidence and
  warnings rather than publication gates.
- Publisher-only publication, independent per portfolio (SOBSTV and TABYS publish separately; `GET /portfolios` reports if their published report dates mismatch).
- Withdraw: a publisher can pull a published version out of operational reads with a mandatory reason, without deleting the source file, snapshot, or audit trail.
- Full audit trail per import (`created`, `validating`, `validated`, `approved`, `rejected`, `published`, `superseded`, `withdrawn`, DQ assignment events).
- Import comparison: diff a validated import against the prior approved version (metric deltas, added/removed/unchanged lots).

## 3. Data quality & exception ownership

- TABYS controls cover NAV arithmetic, NAV/unit reconciliation, missing/stale prices, broken/external formulas and quarantined templates. Unit-history controls cover ordering, duplicates, missing values, discontinuities and stale SAQ status.
- Client sources use normalized exact matching only; unmatched and ambiguous names are DQ findings. Corporate-finance units are flagged rather than guessed. Accounting landing detects formula errors and conflicting dates without publishing finance metrics.
- Cross-source reconciliation stores participating versions, actual values, difference, tolerance, date compatibility and evidence for OSIP-vs-valuation securities/cash and valuation-vs-unit-history NAV.
- Deterministic DQ rule register (DQ-01 through DQ-16 and growing) covering broken calculated fields, duplicate settlements, overdue-but-unresolved settlements, missing stable identifiers, missing price/valuation source, mixed sector taxonomy, incomplete ratings/listing coverage, and trailing empty sheet rows.
- Each finding carries severity, affected fields, and exact source-row evidence (workbook/sheet/row).
- **Exception ownership**: a reviewer can assign an owner and due date to any DQ finding (or clear both), independent of the review-time acknowledgement; `is_overdue` is computed server-side. Requires a reason; rejects a due date with no owner.
- Governed metric definitions (`GET /metrics`) explicitly mark each metric's basis (`source` / `derived` / `unavailable`) so the UI never presents a metric it can't actually support.

## 4. Dashboard pages (frontend)

Six routes, all portfolio/report-date/basis/currency-aware via URL search params:

- **Overview** — portfolio-level KPIs with metric basis, allocation by instrument, version/publication governance panel, upcoming operational calendar.
- **Holdings** — instrument aggregation by ISIN with drill-down to immutable lots (HPR, current YTM, purchase vs. derived-carrying basis toggle). Holdings exports label HPR explicitly as `HPR (расч.), KZT, %` and `HPR (расч.), FX, %`; the lot sheet also retains the corresponding KZT/FX HPR amount columns. Export-only KZT/FX equivalents use the National Bank of Kazakhstan's dated official USD/KZT RSS rate for the report date (or the latest prior published rate within seven days); the workbook records the source URL, effective date and method. If the NBK feed is unavailable, the export transparently falls back to the consistent source-reported OSIP workbook rate; if neither exists, the equivalent remains unavailable. Dashboard carrying-value calculations are unchanged and continue to use the OSIP report FX field. The supplied `classes_and_ratings.xlsx` is represented by the checked-in ISIN-keyed dictionary at `backend/osip_dashboard/data/classes_and_ratings.csv`; it changes presentation classifications only and never overwrites raw source evidence. ETF rows with a source-backed government-bond underlying (for example SGOV/TIP/SPTL/SCHQ) are shown under Government bonds; unresolved classifications remain explicit rather than being silently guessed. The complete column-to-source/formula audit is in [`docs/export-column-audit.md`](export-column-audit.md).
- **Cash & calendar** — cash balances by custodian (native + KZT), a calendar of lot-level dated events (repo/coupon/maturity) with real source purchase amounts on open/purchase events, Excel export. The workbook now includes control notes, active/inactive highlighting, a currency-summary total, a native currency pie chart, and a calendar KZT-total row; “Предстоящие расчёты” remain excluded.
- **Data quality** — filterable/searchable findings table, acknowledgement status, owner/due-date assignment, governed-metric catalogue, Excel export. The export repeats the active filters, preserves workbook/sheet/row evidence, highlights blocker/high and overdue findings, and adds a severity chart when the filtered view contains more than one severity.
- **Imports (source uploads)** — upload form (portfolio code + optional display name), immutable version registry, comparison view, approve/reject/publish/withdraw actions, Excel export of the registry. The registry export now includes a compact status/DQ control line and status highlighting while retaining the two-sheet contract (`Реестр загрузок`, `Аудит`).
- **Reporting** — publication readiness gates, controlled CSV "operational snapshot" export (hash-verified, disclosure-labeled, replay-safe), report history.

Shared shell: collapsible sidebar nav, portfolio/report-date/basis/currency filter bar, domain switch that preserves the current page when valid (and opens that domain's landing page only when necessary), accessible (axe-tested) throughout.

Portfolio Operations Insight domain routes add:

- **Management centre** — source/dataset publication readiness and reconciliation status.
- **Asset management** — source-reported TABYS valuation, holdings and unit history with explicit source manifests/date mismatches.
- **Treasury** — the existing own-portfolio OSIP read model under the broader domain navigation.
- **Brokerage and Clients** — canonical trade, derivative, account, holding, cash and opening-date views; unsupported commission/NNA metrics remain unavailable.
- **Corporate finance** — deterministic mandate register and period summary, not a fabricated CRM forecast.
- **Operations and reconciliations** — child-version readiness and persisted cross-source controls.
- **Accounting / Risk and limits** — accounting shows landing evidence only; Risk exposes source-backed SOBSTV/TABYS limit controls, duration checks, currency/open-FX sections, and workbook exposure detail while keeping VaR, stress, and capital metrics unavailable.

## 5. Localization (RU/EN)

- Full interface localization (`frontend/src/i18n`), English default for new visitors, persisted RU/EN toggle in the top bar.
- Source workbook evidence (filenames, sheet/row references, issuer names, raw values) is deliberately never translated — only the app's own UI chrome and messages are localized.
- Matching bilingual API-message layer (`backend/osip_dashboard/i18n.py`) keyed off `Accept-Language`, defaulting to Russian; error codes and financial values stay language-neutral.

## 6. Command search

- ⌘K / Ctrl+K or clicking the top-bar search opens a command palette.
- Filters page navigation by label, and — once a query is typed — instruments in the current portfolio's published snapshot by ISIN, security code, or issuer.
- Arrow keys to navigate, Enter to activate, Escape/backdrop click to close.
- Selecting an instrument deep-links to Holdings with that instrument pre-filled in the existing table filter (via a `term` URL param), including when already on the Holdings page.

## 7. Exports

| Export | Format | Where |
|---|---|---|
| Operational snapshot | CSV | Reporting page — gated on published + all critical DQ acknowledged, hash-verified, replay returns the same artifact |
| Instrument holdings | XLSX | Holdings page — respects active search/asset-class filter and value basis |
| Position lots | XLSX | Holdings page |
| Cash & calendar | XLSX | Cash & calendar page |
| DQ findings | XLSX | Data quality page — respects active search/severity filter |
| Import registry | XLSX | Imports page |
| TABYS fund data | XLSX | Asset management — published valuation, holdings and unit-series sheets |
| Brokerage data | XLSX | Brokerage — published trade and derivative sheets |
| Client data | XLSX | Clients — full authorized identifiers, explicitly audited |
| Corporate-finance register | XLSX | Corporate finance |

Domain-page Excel exports pass the active table search term to the server and record the filtered row count in the export audit event.

## 8. Identity & access control

## 8.1 Metric provenance

- Source and derived basis badges on the published portfolio, holdings, cash,
  and operations views are interactive. Clicking one opens the provenance
  drawer rather than relying on a generic disclosure.
- `GET /api/v1/snapshots/{snapshot_id}/provenance` returns the exact workbook,
  sheet, row, parser version, source-row ID, parsed field, and value for each
  OSIP overview metric. Derived values also expose their formula and the input
  metrics used by it. Unavailable metrics explain which required source inputs
  are absent.
- Operations registry aggregates identify the contributing source filenames and
  dataset scope; they are explicitly marked as registry aggregates when no
  single business row can represent the value.
- Every interactive `Источник`/`Source` badge now opens a provenance drawer
  with the available workbook, sheet, row, column and cell coordinates. OSIP
  overview, holdings, cash, calendar and DQ metrics use field-specific cells;
  domain KPI/chart badges include the published dataset manifest plus the
  row-level references returned by that domain. Aggregate cards are labelled
  as aggregates rather than pretending that one cell contains the total.
- Original workbook names, sheet names, issuer text, and raw values are shown
  unchanged; only explanatory UI text follows the RU/EN switch.
- A published overview total is never silently partial: if any current lot is
  missing its carrying amount (AA) or report FX rate (AU), derived carrying
  value and operational total are shown as unavailable and the provenance
  window lists the exact missing cells. The affected data-quality finding
  remains the route to correction.
- The provenance drawer previews the first 40 references for responsiveness
  and provides **Show all references** when a full aggregate needs to be
  inspected. Static policy labels are not interactive; only an actual metric
  or chart opens a calculation/source window.
- Treasury, brokerage, and client charts that are tagged as derived expose
  their explicit calculation rules, exclusions, and contributing published
  records in the provenance window. For example, the client asset chart uses
  `securities = total assets KZT − cash KZT` per client and does not clamp a
  negative residual to zero.

- Four roles: `uploader`, `reviewer`, `publisher`, `reader`, enforced per-endpoint.
- Portfolio-scoped access (`X-Actor-Portfolios` in development; a signed claim in production) — a reader restricted to one portfolio can't see another's imports or snapshots.
- Fund and portfolio child datasets reuse portfolio-scoped access. Client-detail URLs use opaque record UUIDs; account/IIN values are excluded from URLs, logs, telemetry, exception text and audit parameters.
- Local development: identity via `X-Actor-Id`/`X-Actor-Roles` headers.
- Production: signed OIDC bearer tokens only (asymmetric algorithms, issuer/audience/expiry validated, explicit external-role → app-role mapping); the development header path is refused outright when `OSIP_ENVIRONMENT=production`.

## 9. Operations & production readiness

- Prometheus metrics and structured health endpoints (`/health`, `/health/live`, `/health/ready`).
- Security response headers (CSP, HSTS in production, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`).
- Real (non-mocked) backup/restore verified end-to-end against actual PostgreSQL: `pg_dump`/`pg_restore`, full migration chain, seeded real data via the app's own services, destructive wipe, restore, and reconciliation-tool verification of zero drift.
- Capacity/concurrency probe tooling (`scripts/capacity_probe.py`), including a concurrent-idempotent-upload check.
- Non-root, hash-locked, pinned-base Docker images for both backend and frontend; production nginx has correct SPA fallback (`try_files ... /index.html`) and locked-down ingress headers.

## 10. Local demo & onboarding

- One double-click launchers (`start-dashboard.command` / `.bat`, `stop-dashboard.command` / `.bat`) that bootstrap a Python venv, install the backend unpinned (portable across platforms), start a persistent local demo, and open the browser — no Node, Docker, or PostgreSQL required to just look at the dashboard.
- The persistent demo (`scripts/demo_service.py` + `scripts/e2e_backend.py`) auto-imports both supplied OSIP workbooks and generates sanitized multi-source examples in an ignored local SQLite database. It never reads or copies the ignored real `sources/` files.
- `frontend/dist/` is committed prebuilt, so viewing the demo never requires a Node install.

## 11. CI / quality gates

- Backend: hash-locked dependency install, `pip-audit`, full pytest suite (including a real-Postgres integration test), a guard script (`scripts/check_tracked_sources.py`) that fails if a real source file has been silently swallowed by a `.gitignore` pattern.
- Frontend: `npm audit`, generated-OpenAPI-contract drift check, unit tests, production build, full Playwright e2e suite (accessibility scans per page, workflow interactions, real Excel/CSV export downloads, command search).
- Containers: backend and frontend release images build and boot-check in CI; nginx config syntax-checked.
- A manual (`workflow_dispatch`) job regenerates Playwright's visual baselines on the exact Ubuntu/Chromium environment CI uses, since a baseline captured on a different OS/font stack fails on dimension alone regardless of pixel-diff tolerance.
- `dependency-review` on every pull request.

## 12. OSIP export consistency — 23 July 2026

The cross-export rules for units, provenance, formulas, navigation, notes, and
validation are maintained in
[`excel-export-design-standards.md`](excel-export-design-standards.md).

- Cash, DQ, lot-detail and import-registry workbooks now follow the same
  restrained, source-traceable convention as the holdings and brokerage
  exports: Russian metadata/disclosure, frozen/filterable source tables,
  typed financial values, explicit `Недоступно` values, and visible control
  notes rather than implicit totals.
- Cash exports show the selected-row count and KZT equivalent above the raw
  cash table, a currency-summary total and an editable native Excel pie chart.
  The calendar includes a KZT-only total for rows with a source amount; mixed
  or unavailable native-currency amounts are never silently combined.
- DQ exports visually distinguish blocker/high, medium, acknowledged and
  overdue findings. A severity pie chart is added only when the active filter
  contains at least two severity groups, avoiding a meaningless one-slice
  chart.
- Lot-detail and registry exports keep their existing sheet names and row
  contracts. Their top control lines expose lot/quantity/value totals,
  status counts and critical-DQ counts without changing the immutable source
  rows or audit evidence.
