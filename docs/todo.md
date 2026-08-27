# Master to-do list — path to a complete Portfolio Operations Insight

This is the single consolidated backlog. It does not repeat detail already
maintained elsewhere — it indexes those documents and adds the concrete,
currently-open engineering items that aren't tracked anywhere else yet.
When you finish an item that has a source doc, update that doc too so this
list doesn't drift the way `docs/functionality-breakdown.md` did.

Source documents this list draws on:

- `docs/product-feature-gap-register.md` — canonical product-scope gap
  analysis against the Portfolio Operations Insight reference demo (RU, P0/P1/P2).
- `docs/production-readiness-checklist.md` — release go/no-go sign-off gate.
- `docs/bug-hunt-log.md` — this session's systematic QA sweep, section by
  section; a couple of items were investigated and deliberately left open.
- `docs/uat-and-reconciliation-plan.md`, `docs/security-and-dependency-policy.md`,
  `docs/requirements-traceability.md`, `docs/implementation-plan.md`,
  `docs/operations-runbook.md`, `docs/deployment-runbook.md`.

## 0. Immediate housekeeping

- [x] Commit the in-progress holdings-export distribution/pie-chart feature
      in `backend/osip_dashboard/services/holdings_export.py` — functionally
      complete and documented in `docs/bug-hunt-log.md` §12. (Note: the
      working tree had since grown a second, separate in-progress feature —
      a metric-provenance/explainability endpoint, backend-complete but not
      yet wired into any UI page. Committed alongside since it was internally
      consistent and all tests passed; the UI for it is still unbuilt.)
- [x] Commit or discard the other files currently sitting modified in the
      working tree (`docs/bug-hunt-log.md`, `docs/feature-inventory.md`,
      `tests/test_snapshot_api.py`) so `main` reflects a single consistent
      state.

## 1. Open engineering items (found, not yet fixed)

Each of these was investigated this session and specifically left open —
they are not hypothetical:

- [x] Enforce per-uploader source visibility for multi-operator domains:
      `_has_dataset_access`/`_require_dataset_access` now also require
      `dataset.uploader_id` to match the actor; `latest_published`/
      `module_payload` thread an `uploader_id` filter so current/latest
      selection, source-download/materialization, and pinned-version routes
      are all scoped to the actor's own uploads. A governance/admin bypass
      (the literal `"admin"` role) now exists in `_has_uploader_access` for
      the cross-uploader case. See `docs/domain-upload-instructions.md`.

- [ ] Apply the workbook navigation standard to any future export generator:
      continuous tables freeze their title/header rows and column A, while
      stacked or non-tabular sheets document their deliberate exception in
      `docs/export-column-audit.md`.

- [x] Closed the navigation-standard gap on `multi_source_export.py`'s six
      module summary sheets and the shared `Данные графиков` appender (none
      set `freeze_panes` at all); `Уникальные позиции ETF` was a genuine
      continuous table missing the header-row rule. Coverage across both
      export modules is now complete — see `docs/export-column-audit.md`.

- [x] Make holdings HPR units explicit: exports now include separate
      `HPR (расч.), KZT, %` and `HPR (расч.), FX, %` columns alongside the
      KZT/FX HPR amounts; the FX basis is the USD-equivalent return where
      supported, and the HPR audit script checks both percentage columns.

- [x] Add expected Bloomberg dividend rows to `Ожидаемые денежные потоки`:
      use `pay_date`, require ownership on `ex_date`, apply the existing US
      withholding rule, and disclose Bloomberg dictionary freshness.

- [x] `_is_overdue` (`backend/osip_dashboard/api_handlers.py`) computed
      overdue DQ status from `date.today()` (server-local timezone) instead
      of UTC. Fixed: now uses `utcnow().date()` (the same helper the rest of
      the app uses for `validated_at`/`approved_at`/`published_at`).
      (`bug-hunt-log.md` §3)
- [x] `scripts/demo_service.py`'s `_is_running()` checked only
      `os.kill(pid, 0)` — it didn't verify port ownership, so it could report
      "running" while the HTTP port was actually dead. Fixed: `_is_running`
      now takes an optional `port` and requires `/health` to respond;
      `_remove_stale_state()` passes it, `stop()`'s shutdown poll doesn't (it
      only needs to know the process exited). Reproduced the exact false
      positive and confirmed the fix corrects it; added
      `tests/test_demo_service.py`. (`bug-hunt-log.md` §10, follow-up)
- [x] `scripts/e2e_backend.py`'s `spa_fallback` handler built a filesystem
      path from the raw URL with no `.resolve()` + ancestry check. Fixed:
      applies the same guard as `LocalBlobStore.path_for`. Re-ran the raw-socket
      traversal PoC from the bug-hunt log against the live demo — still safely
      falls through to `index.html`, now by explicit design rather than by
      relying on ASGI's own normalization. (`bug-hunt-log.md` §10)
- [x] The synthetic client/brokerage demo fixture
      (`backend/osip_dashboard/services/demo_multi_source.py`) was down to a
      thin 2-client, 1-position stub with no `client_maturity_calendar` or
      `client_dashboard_snapshot` data at all — a real gap once the actual
      source workbook (`Клиентский_дашборд.xlsx`) was deleted from `sources/`
      and this synthetic seed became the only client/brokerage data the demo
      has. Fixed: factored the seed into `_seed_brokerage_demo` (8 clients
      across 3 managers, 10 positions, 7 trades, 3 derivatives, 8
      open-dates, plus the two missing dataset types, all internally
      consistent and shaped to match the real parser's payload), and added
      `_upgrade_thin_brokerage_demo` so an already-seeded demo database
      (e.g. `.data/demo-deployment`) picks up the richer data too, not just
      a freshly-seeded one. Any future edit to this fixture should go
      through `_seed_brokerage_demo` and extend the upgrade path the same
      way, since `seed_multi_source_demo`'s full-reseed body never runs
      again once a database has any data.

- [x] Both Dockerfiles pin to version tags, not content-addressed digests
      (`@sha256:...`). **Decided 2026-08-11**: keep floating version tags.
      Pinning to a digest would freeze the image and stop it from ever
      receiving upstream security patches under that tag; the user chose
      automatic patch freshness over byte-for-byte build reproducibility.
      No code change - the existing `FROM ...:<tag>` lines are already the
      chosen policy, not an oversight.
      (`bug-hunt-log.md` §9)
- [x] Mobile text-wrap on the top search bar: the label wrapped to two lines
      on narrow viewports, visually cramping the button. Fixed with
      `overflow: hidden; white-space: nowrap; text-overflow: ellipsis` (plus
      `flex: 1; min-width: 0` so the ellipsis can actually engage inside the
      flex row). Verified with a mobile-viewport screenshot before/after.
- [x] Investigated the `charts-*.js` vendor chunk (~421KB, 121KB gzip). Only
      one file (`DomainCharts.tsx`) imports from `recharts`, and it's already
      isolated into its own chunk, loaded only when a route dynamically
      imports it — confirmed via `dist/index.html`: the chunk is referenced
      as `<link rel="modulepreload">`, not a blocking `<script>` tag, so it
      never delays initial execution. The 421KB is recharts' own inherent
      size (it pulls in several d3 submodules internally); there's no
      further free win here without either swapping the charting library
      (a real product decision — recharts is otherwise working fine) or
      tuning Vite's modulepreload eagerness (marginal gain, adds real risk
      of regressing prefetch for the routes that do use it). Not pursuing
      further without a specific complaint (e.g. a slow-connection user
      report) to weigh against that risk.
- [x] Broadened the automated accessibility scan from
      `wcag2a/wcag2aa/wcag21a/wcag21aa` to also include `wcag22aa` and
      `best-practice` axe-core tags. The WCAG tags themselves found nothing
      new; `best-practice` surfaced two real, reproducible issues, both
      fixed: the topbar filterbar wasn't contained in any landmark region
      (converted its wrapper `<div role="group">` to a labelled `<section>`,
      which gets an implicit landmark role) and the comparison page's
      governance table had an empty corner `<th>` (given a real label). A
      full manual keyboard-only + screen-reader workflow walkthrough is
      still open — not attempted this pass.

## 2. Production readiness (release gate)

Full detail and sign-off tracking: `docs/production-readiness-checklist.md`.
The concrete engineering work implied by its unchecked boxes:

- [ ] Register the real IdP client (issuer/audience/JWKS, PKCE redirect URIs,
      logout/session policy) and wire signed role/portfolio claim mapping —
      today only local dev-identity headers exist.
- [ ] Run the PostgreSQL 16 migration on a clean production-like environment;
      rehearse rollback and forward recovery.
- [ ] Run a production-like concurrency/capacity test against agreed SLOs.
- [ ] Stand up encrypted backup + off-site copy + retention/key custody, and
      run a real isolated restore drill within RTO.
- [ ] Wire liveness/readiness dashboards, log aggregation, alert rules, and
      on-call routing; test them, don't just configure them.
- [ ] Write incident / failed-import / DQ-escalation / recovery / rollback
      runbooks with named owners (some runbook content exists in
      `docs/operations-runbook.md` — confirm it's complete and has owners).
- [ ] TLS, ingress restrictions, CORS, CSP, secrets rotation, DB network
      policy, and `/metrics` isolation — get these reviewed and approved,
      not just implemented.
- [ ] Commission dependency / application / infrastructure / penetration
      test review evidence (`docs/security-and-dependency-policy.md` has the
      policy; this is the actual review execution).
- [ ] Execute UAT-01 through UAT-15 (`docs/uat-and-reconciliation-plan.md`)
      with named sign-off; confirm both source hashes and every
      reconciliation baseline pass.
- [ ] Confirm browser/device scope and get visual baselines formally
      accepted (the Playwright visual-baseline suite already runs in CI,
      gated to Ubuntu — see `frontend/e2e/dashboard.spec.ts:107`).

## 3. Product/platform scope (Portfolio Operations Insight parity)

**Scope decision (confirmed 2026-07-29): this dashboard works from uploaded
workbooks only, permanently.** An operator uploads a workbook; the app
parses and discloses it (`source`/`derived`/`unavailable` basis on every
value). It does not, and will not, integrate live with external systems of
record — no custodian feed, no trading-system connection, no GL push, no
settlement-system integration. Every item below that assumes such a live
integration is **out of scope by design**, not merely unscheduled, and
should not be picked up without this decision being explicitly reopened.
`docs/product-feature-gap-register.md` was written against the
system-integration assumption and should be read (or revised) with that in
mind — its P0/P1/P2 labels no longer reflect what's actually buildable here.

**Out of scope by design** (assumes a live external system feeding the app,
not a workbook a person uploads):
- Portfolio/account/instrument master data as a real system of record — a
  workbook-derived identity is the permanent model here, not a stand-in for
  one
- An "official" valuation & FX feed, a transaction/execution ledger, or a
  settlement/cash reconciliation platform sourced from anywhere but an
  uploaded workbook
- Treasury market/book valuation beyond the current derived carrying value
- Benchmark performance (needs a live external index feed)
- Clients/CRM/invoices/KYC as a live system integration
- Group management P&L / consolidation GL, a corporate-finance deal-pipeline
  CRM, a real VaR/stress-testing risk framework, a KYC/AML compliance module
- AI analyst gated on "governed metrics, lineage, DQ, and permissions are
  real" in the system-of-record sense above

**Resolved 2026-07-29 — struck from the backlog, not just deferred:**
- ~~Reporting factory: template engine, PDF/XLSX rendering, submission
  receipts~~ — the actual need was per-domain Excel export, which already
  exists: 7 export functions (Risk, Accounting, Corporate Finance,
  Brokerage, Cash Calendar, Holdings Lots, DQ issues), each producing a
  real formatted workbook via `create_module_xlsx`/`_module_export`. A
  job queue, watermarking, archival/hashing, and a template engine are
  enterprise report-distribution infrastructure with no demonstrated need
  here; the due/ready/blocked/overdue register itself shipped as the
  Operations readiness panel.
- ~~DQ platform maturity: a lineage view across dataset versions~~ — this
  app has no maker/checker audience: visibility is uploader-scoped by
  design (an operator only ever sees their own uploads), so there is no
  "who did what to data I don't otherwise see" question for a lineage
  view to answer. Freshness SLAs and remediation (`services/action_items.py`)
  already shipped; the lineage-view portion specifically doesn't apply here.
- ~~Income/corporate-actions/ratings feed as an uploaded reference
  workbook~~ — speculative. The one reference-data pattern that exists
  (the dividend dictionary) mirrors a real external workflow (a Bloomberg
  export gets uploaded); there's no analogous real corporate-actions
  source behind this idea, so it would be scaffolding without a source.
- ~~Historical NAV/position/flow tracking~~ — already exists:
  `fund_unit_series`/`fund_nav_history` under Asset Management, plotted
  as a history chart, plus the Risk breach trend shipped this session.

**Cross-cutting, workbook-model-compatible:**
- [ ] Production RBAC/ABAC (entitlements, masking, segregation of duties —
      beyond today's local roles + OIDC interface)
- [ ] Notifications/inbox (event bus, preferences, delivery log)
- [ ] Full RU/KZ/EN i18n (KZ doesn't exist yet; current i18n covers RU/EN)
- [ ] Real export platform: a PDF path, a download job queue, archival/
      hashing, and watermarking — only if an actual need shows up. Every
      domain already has a real, formatted per-module Excel export (see
      §3's resolved reporting-factory note); this bullet is the residual
      enterprise-distribution layer on top of that, not a gap in exporting
      itself.
- [ ] Saved views (persisted filter snapshots with owner/shared scope)
- [ ] Unified design system pass: reusable components, responsive policy,
      visual regression, RU microcopy glossary

## 4. Open product decisions (blocking further platform work)

The workbook-only scope decision above resolves one of the gap register's
original open questions directly:

- [x] What are the systems of record for master data, valuation, trading,
      settlement/cash? — There are none beyond the uploaded workbook itself;
      the app discloses basis (source/derived/unavailable) rather than
      claiming an authority a workbook can't provide.

Still open, and still needing a product owner rather than an engineer:

- [ ] Which demo modules are actually in scope — Finance, Deals, Brokerage,
      Clients — versus separate products? (KYC/AML is resolved as out of
      scope per §3, since it inherently requires a live compliance system.)
- [ ] What's the first official metric to build from workbook evidence —
      derived NAV, market value, AUM, something else — and who approves the
      methodology given it will always carry a "derived, not official"
      basis rather than a system-of-record one?
- [ ] Are regulatory submissions required in the first target release, or
      is internal operational reporting the first milestone?
- [ ] What privacy/data-residency/masking/export controls apply to
      client-level data uploaded in a workbook?
- [ ] What refresh cadence is required per domain — intraday, EOD, T+1,
      month-end? (Bounded by upload cadence rather than a live feed in this
      model.)
