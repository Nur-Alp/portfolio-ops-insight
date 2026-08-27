# Portfolio Operations Insight — Tracked Implementation Plan

This is the tracked execution checklist for the delivery plan in `internal/osip-portfolio-dashboard-feasibility-and-delivery-plan.md`. The visual/interaction reference is `internal/functionality-template/`; the workbook truth and DQ register are in `internal/osip-workbook-dashboard-readiness-analysis.md`. Those source references are intentionally Git-ignored, while this status document and the implementation are tracked.

## Product guardrails

- Product position: local, domain-owned analytics and reporting; not official fund accounting, a trading system or a risk engine. A hosted multi-user deployment would require a separate security review.
- Portfolios: `SOBSTV` and `TABYS`; reporting currency `KZT`.
- Value name: **Derived carrying value** using `AA × AU × AT + AR`.
- Metric bases: `source`, `derived`, or `unavailable`.
- Unsupported until authoritative sources arrive: accounting-approved NAV/performance, P&L attribution, formal order/execution and settlement reconciliation, commissions/NNA, production risk/compliance, corporate actions, and fee billing.
- Local operating role: one responsible domain owner. Non-OSIP source-first data is readable after successful parsing; client matching and four-eyes publication are optional. The legacy `uploader`, `reviewer`, `publisher`, and `reader` roles remain for OSIP tests and a future hosted deployment.
- `port-acc` and the captured public site are references, not source trees to copy into the product. Organizational reuse/design approval remains a release-governance responsibility.

## Phase 0 — Decisions and controlled baseline

Status: complete for engineering; external provenance confirmation remains a release gate.

- [x] Clean tracked application at the repository root; development does not occur inside ignored `internal/port-acc`.
- [x] SOBSTV/TABYS identities and KZT reporting currency defined.
- [x] Metric name, formula, bases, unavailable metrics, and roles documented.
- [x] Selective-reference decision: independent OSIP model and UI; no direct loading into `port-acc` accounting tables and no reuse of its demo database.
- [ ] Organization records final permission/provenance approval before production release.

Evidence: `README.md`, `backend/osip_dashboard/config.py`, `backend/osip_dashboard/persistence/models.py`.

## Phase 1 — Data foundation

Status: complete.

- [x] PostgreSQL 16 development service and Alembic migration.
- [x] Immutable SHA-256 source storage and idempotent import batches.
- [x] Tolerant legacy `.xls` parser with stable-column and content-row classification.
- [x] Immutable raw-row lineage with workbook, sheet, row, parser version, and exact original file retrieval.
- [x] Position lots, cash, sections, raw/deduplicated settlements, DQ findings, acknowledgements, and audit persistence.
- [x] Deterministic workbook DQ register, including blocker/high rules, rating/listing coverage, helpers, ambiguous thresholds, missing custodians, stale metadata, and source-header defects.
- [x] Immutable versions, independent dataset publication, and supersession. Four-eyes approval remains available for OSIP/hosted workflows but is not required for local source-first domain views.
- [x] Import preview and comparison to the latest prior approved snapshot.
- [x] Golden acceptance totals and row insertion/reordering tests.

Evidence: `backend/osip_dashboard/ingestion/`, `backend/osip_dashboard/services/`, `migrations/`, `tests/`.

## Phase 2 — Dashboard API and design system

Status: complete.

- [x] Snapshot overview, lot holdings, cash, settlements, DQ, imports, source retrieval, and portfolio APIs.
- [x] Decimal-string and ISO-date API guardrails; source/derived/unavailable overview bases.
- [x] Canonical instrument aggregation/read model and governed metric definitions.
- [x] Calendar API for settlements, maturities, coupons, and repo dates.
- [x] Report-readiness API with DQ/approval gates.
- [x] Split route declarations by imports/catalog/snapshots/reports and publish validated response schemas plus a generated, CI-drift-checked OpenAPI TypeScript client contract.
- [x] React/TypeScript application foundation with locked dependencies and CI build.
- [x] Design tokens, responsive shell, URL-backed global filters, KPI cards, tables, drawers, charts, pills, and standard states.
- [x] Keyboard/accessibility audit and live visual-regression suite, including all routes, evidence drawers, desktop/mobile references, and serious/critical WCAG checks.

Reference behavior: the captured `/dashboard`, `/treasury`, `/operations`, `/data-quality`, and `/reporting` pages. Recreate their interaction grammar with maintainable source; do not use the minified production bundles as application source.

## Phase 3 — Interactive MVP pages

Status: complete for the workbook-only interactive MVP.

- [x] Portfolio Overview.
- [x] Holdings with aggregated instruments and lot/source drawer.
- [x] Cash & Calendar.
- [x] Data Quality with evidence/lineage drawer.
- [x] Source Imports preview, comparison, independent approval, and publish journey.
- [x] Reporting readiness, persistent report runs, and controlled reproducible CSV snapshot export.
- [x] End-to-end workbook-to-published-dashboard journey using both real workbooks in a disposable live browser environment.

## Phase 4 — Hardening and UAT

Status: partially established, not production-ready.

- [x] Durable audit events and four-eyes workflow.
- [x] API roles and production rejection of development identity.
- [x] PostgreSQL CI service and parser/API/migration golden tests.
- [x] Signed OIDC bearer validation, browser authorization-code/PKCE handoff, explicit role mapping, and portfolio-level list/direct-object enforcement.
- [ ] Register the organization IdP client and approve redirect URIs, claim contract, group assignments, key rotation, session policy, and access-control UAT.
- [x] Hash-pinned Python and npm locks, registry audits, CI dependency review, and weekly automated update proposals.
- [x] Non-root backend/OIDC-frontend release images, confidential build-context exclusions, one-shot migration deployment, public security headers, development-header stripping, and private `/metrics` boundary.
- [x] Current-workload and upload-boundary performance guards; external HTTP concurrency/idempotency probe; verified database/blob backup and restore tooling; readiness, request telemetry, Prometheus alerts, and incident runbooks.
- [ ] Complete a production-like concurrency test and real PostgreSQL recovery drill; approve RPO/RTO, retention, encryption, and on-call routing.
- [x] Visual regression, browser E2E, and accessibility suites in CI.
- [ ] Business UAT, reconciliation sign-off, operational owners, and production checklist.

Execution artifacts: `docs/uat-and-reconciliation-plan.md`,
`docs/production-readiness-checklist.md`, and `docs/requirements-traceability.md`.

## Later releases — blocked by missing authoritative data

Do not enable these merely to complete navigation: accounting-approved NAV/performance, formal settlement reconciliation, commissions/NNA, risk/limits, compliance, fees/payables, corporate actions, or AI analysis. Each requires the additional structured sources and business definitions listed in the workbook-readiness reference.

## Phase 5 — Multi-source Portfolio Operations Insight

Status: implemented for currently supplied source classes; complete accounting and risk remain pending.

- [x] Immutable physical source uploads, content detection, independent child versions, backfill migration and OSIP-compatible wrappers.
- [x] TABYS valuation/holdings/cash-liability/history/price and SAQ/TABYS unit-series adapters with deterministic DQ and persisted reconciliation.
- [x] Brokerage trades, derivatives, clients/accounts/positions/cash and opening-date adapters with exact-name matching and PII-safe read/export audit.
- [x] Client maturity-calendar and cached client-summary child datasets, with subtotal exclusion, manager distribution and cross-sheet total discrepancy DQ.
- [x] TABYS reconciliation/price-coverage/evidence controls and currency-separated Corporate Finance comparisons; source-backed maturity/coupon/mandate fields are visible in the domain pages.
- [x] Corporate-finance controlled register with deterministic deal key, raw/normalized values and ambiguity controls.
- [x] Accounting landing/DQ evidence and explicit Accounting/Risk pending-source states without invented metrics.
- [x] Portfolio Operations Insight branding, domain navigation, upload wizard, source manifests, date-mismatch warnings and Russian operational XLSX exports.
- [x] Generated sanitized local-demo examples; ignored real source workbooks are never committed or loaded by the demo.
- [ ] Integrate complete accounting and authoritative risk packages when delivered, under new versioned adapters and business-approved metric contracts.
