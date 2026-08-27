# Bug hunt log

> Working log for a systematic pass through `docs/feature-inventory.md`, section by
> section. For each feature: checked for bug possibilities, logged here with a
> status. Status values: `checking`, `clean`, `bug-found`, `fixed`.

## Summary (first full pass, 2026-07-20)

All 11 feature-inventory sections reviewed. Outcome:

- **Fixed this pass:** 3 total.
  1. `services/imports.py` concurrent-upload `IntegrityError` recovery could
     nondeterministically match a stale withdrawn/rejected/failed row instead
     of the real active duplicate (narrow race condition).
  2. `InstrumentRecord` reference data (issuer/sector/asset class) was written
     once per ISIN and never refreshed on re-import — a corrected re-import
     could never fix a wrong Repo-vs-other calendar classification or
     asset-class allocation bucket. `_persist_snapshot` now updates the
     existing row's fields on every import instead of only inserting when
     missing. Added a dedicated regression test
     (`tests/test_instrument_master_data.py`) that persists two synthetic
     snapshots for the same ISIN with different `raw_security_type`/`issuer`
     and asserts the second one wins — confirmed it fails without the fix,
     passes with it.
  3. "Acknowledge and approve" always sent a hardcoded canned justification
     string instead of collecting one from the reviewer, undermining the
     documented "mandatory written justification" four-eyes control. Added a
     required textarea to `ImportsPage.tsx` (mirroring the existing withdraw-
     reason field), wired through `dashboardApi.approve(id, codes, comment)`;
     the button is disabled until the reviewer types something. Verified live
     against the local demo: uploaded a byte-modified copy of the SOBSTV
     fixture under a new portfolio code, confirmed the button is disabled
     with an empty textarea and enabled once filled, and that a real approval
     goes through end-to-end (status flips to "Утверждено", publish action
     appears). Demo runtime state reset afterward to remove the test upload.
  Backend suite green (57 passed, 1 skipped — one more than before, the new
  regression test), frontend unit tests green (17 passed), e2e green (13
  passed, 1 skipped Ubuntu-only baseline).
- **Fixed earlier this session** (found before this systematic sweep started,
  carried here for completeness): governance-gate labels, ~22 missing DQ
  affected-field translations, the entire metric-catalog panel, and audit/
  export timestamp UTC labeling — all localization bugs in section 5/7.
- **Minor notes, not fixed** (low severity / deployment-dependent / cosmetic):
  `_is_overdue` uses server-local `date.today()` instead of UTC; the asset-
  class filter dropdown sorts on the untranslated English key; Docker base
  images are tag-pinned, not digest-pinned.
- **Investigated and ruled out** (real suspicion, verified not exploitable/not
  a bug): the local demo's SPA-fallback path-traversal concern (tested with
  raw-socket requests, confirmed the ASGI layer normalizes dot-segments); the
  production dev-identity-provider guard (confirmed the real enforcement is
  `config.py`'s `Settings` validator, not the `create_app()` isinstance check
  that looked bypassable).
- **Everything else** (parsing engine, DQ rule register, exception ownership,
  command palette, exports, CI workflow) reviewed and found correct.

## 1. Workbook ingestion & parsing
- Status: clean (reviewed `osip_workbook.py` in full: header discovery, section
  classification, cash-row parsing regex, BROKEN_CALCULATED_FIELDS/DQ-01,
  settlement dedup/DQ-02, DQ-03/04/05/07/12/16, HPR/current_ytm aggregation in
  `api_handlers.py`. No incorrect logic found; edge cases like zero-quantity
  rows, ambiguous multi-lot current_ytm, and zero purchase amount are handled
  deliberately (documented behavior), not bugs. Backed by golden regression
  tests against both real workbooks.)

## 2. Import & publication workflow
- Status: fixed 1, found 1 (needs product decision)
- **[fixed]** `import_workbook`'s `IntegrityError` recovery query
  (`services/imports.py`, concurrent duplicate-upload race) queried for an
  existing `ImportBatch` by `(source_sha256, portfolio_code)` without
  excluding withdrawn/rejected/failed rows, unlike the pre-insert duplicate
  check just above it. Since the unique index is partial (only covers
  active-status rows), a stale withdrawn/rejected/failed row for the same
  `(sha256, portfolio)` can coexist with the concurrent winner that actually
  caused the conflict — `session.scalar()` on a query matching 2 rows
  silently picks one without error, so the race could nondeterministically
  report the dead row as "the duplicate" instead of the real active one.
  Fixed by adding the same `status.not_in(non_blocking_statuses)` filter used
  in the pre-insert check. Narrow/rare (needs a real concurrent race *and* a
  prior withdrawn/rejected/failed record for the same bytes+portfolio), but a
  genuine correctness gap in exception-recovery logic. Backend test suite
  still green after the change (no existing test exercised this exact path).
- **[fixed]** `InstrumentRecord`
  (`persistence/models.py`, table `instruments`, keyed by ISIN only) was
  written **once** per ISIN in `_persist_snapshot` (`services/imports.py:363-377`,
  `if session.get(InstrumentRecord, position.isin) is None: session.add(...)`)
  and never updated afterward. Its fields (`issuer`, `raw_security_type`,
  `normalized_asset_class`, `instrument_currency`, `raw_sector`,
  `security_code`) are read live on every request via the `lot.instrument.*`
  relationship — including `normalized_asset_class`, which decides asset-class
  allocation buckets (Overview "Portfolio structure") **and** whether a
  calendar event is labeled `repo_open/repo_close` vs. `instrument_open/maturity`
  (`services/reporting.py:182,185`). Because the record is created from the
  *first* import that ever introduces that ISIN — including a `DRAFT`/
  `VALIDATING` import that's later rejected, since `_persist_snapshot` runs
  before approval — any later, corrected re-import of the same instrument
  (fixed issuer spelling, corrected sector/asset class, etc.) silently keeps
  showing the old, possibly-wrong classification forever, across every
  portfolio that later holds that instrument. This may be deliberate MDM-style
  design (the field is literally named `first_seen_at`), matching the
  documented P0 gap "Instrument master" in
  `docs/product-feature-gap-register.md` — i.e. this table might have
  been intended as a stand-in for a not-yet-built curated master-data
  contract, not accidentally-stale cache. Raised to the user, who chose to
  fix it: `_persist_snapshot` now updates the existing `InstrumentRecord`'s
  fields (`security_code`, `issuer`, `raw_security_type`,
  `normalized_asset_class`, `instrument_currency`, `raw_sector`) to match the
  latest parsed snapshot on every import, matching the app's "always reflect
  the latest source" philosophy used everywhere else. Covered by a new
  regression test (`tests/test_instrument_master_data.py`), confirmed to fail
  without the fix and pass with it.
- Rest of `services/workflow.py` (approve/reject/withdraw/publish/assign_dq_issue)
  and the remainder of `services/imports.py` (validation, `_persist_snapshot`
  money aggregation, source-row dedup) reviewed line by line — four-eyes
  check, mandatory-reason checks, per-report-date supersede-on-publish scoping,
  and the previously-fixed withdrawn-reimport partial unique index all read
  correctly. No further issues found.

## 3. Data quality & exception ownership
- Status: clean, 1 very minor note
- Reviewed `_is_overdue`, `assign_dq_issue` handler + service, portfolio-scoping
  (`_get_dq_issue` → `require_portfolio`), acknowledgement payload shape.
- **[minor note, not fixed]** `_is_overdue` (`api_handlers.py:1131`) uses
  `date.today()` (server local timezone) rather than a UTC-based date, while
  the rest of the app is consistently UTC (`utcnow()`). Only matters if the
  server's OS timezone isn't UTC, in which case a due date could flip overdue
  status up to ~1 day early/late right at the boundary. Very low severity,
  deployment-config-dependent; not fixed since it may never manifest in
  practice (containers typically run UTC) and touching it without knowing
  the real deployment timezone risks a no-op or wrong assumption.
- Role/ownership rules match spec: only `reviewer` role can assign/clear
  owner+due date; portfolio-scoped access enforced before mutation.

## 4. Dashboard pages (frontend)
- Status: 1 significant bug fixed, 1 minor note
- **[fixed]** `ImportsPage.tsx`'s
  "Acknowledge and approve" button called `dashboardApi.approve(id, codes)`
  (`frontend/src/api/client.ts:237-244`), which **hardcoded** the mandatory
  approval justification: `comment: "Проверено в соответствии с политикой
  операционных данных OSIP"` — the same canned Russian string every time,
  for every reviewer, in every environment (this is not the demo-only client;
  it's the one production build uses too — actor identity is correctly
  swapped for a real OIDC bearer token in `VITE_AUTH_MODE=oidc`
  (`auth/session.ts`), but the comment text is not identity-dependent and is
  never sourced from user input anywhere). The backend genuinely enforces
  "non-empty justification" (`services/workflow.py: if not justification:
  raise WorkflowError(...)`), and the feature inventory documents "mandatory
  written justification" as a real four-eyes control — but the frontend never
  renders a textarea for the reviewer to type one (unlike the withdraw flow,
  which does have a `<textarea>` for its reason). The backend's structural
  check is satisfied, but the actual accountability record is fake: every
  approval in this app, ever, carries the identical, meaningless canned
  sentence rather than a real reviewer justification. This is either (a) an
  unfinished feature — the review-justification textarea was never built —
  or (b) an intentional demo simplification never updated for the real
  workflow. Given the compliance-control framing in the inventory, this was
  significant enough to raise to the user rather than silently guess the
  intended UX — user chose to add the missing control. Fixed by adding a
  required "Обоснование утверждения" / "Approval justification" textarea to
  the validated-import drawer (styled with the existing neutral
  `.dq-assignment` class, not the red `.withdraw-action` one, since this
  isn't a destructive action), disabling "Acknowledge and approve" until it's
  non-empty, and threading the typed text through
  `dashboardApi.approve(id, codes, comment)` into the real request body
  instead of the hardcoded string. Verified live: uploaded a byte-modified
  copy of the SOBSTV fixture under a new portfolio code to get a real
  `validated` import, confirmed the button is disabled empty / enabled once
  filled, and completed a real approval (status flipped to "Утверждено").
- **[minor note, not fixed]** `HoldingsPage.tsx`'s asset-class filter dropdown
  (`assetClasses = [...new Set(...)].sort()`) sorts on the raw English
  `normalized_asset_class` value, not the localized label shown in the
  `<option>`. In Russian mode the dropdown order doesn't match Cyrillic
  alphabetical order of what's displayed (e.g. "ETF" sorts before "Government
  bonds" in the underlying English key, unrelated to where "ETF" would fall
  among the Russian labels). Cosmetic ordering only, not a functional bug;
  left as-is pending a decision on whether dropdown order is worth a
  locale-aware sort.
- `OverviewPage.tsx`, `CashCalendarPage.tsx`, `DataQualityPage.tsx`,
  `ReportingPage.tsx` reviewed fully: query `enabled` guards, null/undefined
  handling, drawer state resets, and basis-toggle key selection (`valueKey`/
  `weightKey`) all correct. No further issues found.

## 5. Localization (RU/EN)
- Status: fixed 3 (earlier this session) + verified clean this pass
- Earlier this session: fixed missing `humanize()` labels for governance gates
  (`independent_approval`, `critical_dq_acknowledged`), ~22 missing DQ
  affected-field labels (portfolio_id, price_source, raw_sector, etc.), the
  entire "Controlled metrics" catalog panel (was English-only regardless of
  language toggle), and relabeled audit-export timestamps as explicit UTC.
- This pass: cross-checked every `t("...")` call site across `frontend/src`
  against the `i18n/index.tsx` catalogue programmatically — 184 unique keys
  used, all 184 present in the catalogue, and all 203 defined catalogue
  entries have both `ru` and `en` non-empty. No missing-translation-key gaps
  remain in the `t()` path (separate from the `humanize()` labels dict, which
  was the source of the earlier bugs and is now also exhaustively covered for
  every `affected_fields`/gate/metric value actually produced by the backend).

## 6. Command search
- Status: clean
- Reviewed `CommandPalette.tsx` and its `AppShell.tsx` wiring in full: ⌘K/Ctrl+K
  binding, focus management on open, Escape/backdrop close, arrow-key/Enter
  navigation with clamped index, nav-vs-instrument item filtering, and the
  `term`-param deep link to Holdings (previously-fixed same-route sync bug
  verified still correct). No issues found.

## 7. Exports
- Status: clean (1 bug already fixed earlier this session — audit/registry/DQ
  timestamp UTC labeling)
- Reviewed `services/reporting.py` (CSV operational snapshot: DQ-acknowledgement
  gate re-checked at generation time, content-hash dedup/replay semantics —
  confirmed safe since embedded Import ID/SHA-256 make cross-snapshot content
  collisions practically impossible) and the rest of `services/holdings_export.py`
  (instruments/lots/cash+calendar/DQ/registry XLSX builders). Excel exports are
  deliberately Russian-only regardless of UI language toggle — an intentional,
  already-documented design choice, not a bug. No further issues found.

## 8. Identity & access control
- Status: clean
- Reviewed `identity.py` (`DevelopmentHeaderIdentityProvider`,
  `OidcIdentityProvider` claim mapping/validation, `require_role`,
  `require_portfolio`) and `security.py` in full.
- Specifically chased down a suspected gap: `main.py`'s `create_app()` only
  raises if an explicitly-injected `identity_provider` argument is a
  `DevelopmentHeaderIdentityProvider` while `environment == "production"` —
  and the real server entrypoint (`main.py:139`, `app = create_app()`) never
  passes that argument, so that particular check looked like it could never
  fire in a real deployment. Traced further and found the actual enforcement
  point is `config.py`'s `Settings.reject_development_identity_in_production`
  `model_validator`, which unconditionally raises at `Settings()` construction
  (used by `get_settings()`, which `create_app()` calls whenever no explicit
  settings are passed) if `environment == "production"` and
  `identity_provider == "development"` are ever combined. That validator also
  covers non-Postgres-in-production, incomplete/insecure OIDC config, and
  wildcard/non-HTTPS CORS in production. So the invariant documented in the
  feature inventory ("the development header path is refused outright when
  OSIP_ENVIRONMENT=production") does hold in practice — confirmed clean, not
  a bug.
- OIDC role mapping is explicit allow-list only (unmapped external roles are
  silently dropped, never granted); portfolio scoping fails closed (empty
  claim → empty `portfolios` set → every portfolio-scoped check denies).

## 9. Operations & production readiness
- Status: clean, 1 documentation-precision nitpick (not a functional bug)
- Reviewed `/health`, `/health/live`, `/health/ready` (DB `SELECT 1` +
  blob-store accessibility check, correct 503 on either failure) and
  `storage.py`'s `LocalBlobStore` (atomic tempfile+fsync+`os.replace` write,
  content-collision detection on matching keys, path-traversal guard in
  `path_for` via `resolve()` + parents check). All correct.
- **[nitpick, not a bug]** Both `Dockerfile` (`FROM python:3.12-slim-bookworm`)
  and `frontend/Dockerfile` (`FROM node:22-alpine`,
  `FROM nginxinc/nginx-unprivileged:1.27-alpine`) pin to specific version
  *tags*, not content-addressed digests (`@sha256:...`). The feature inventory
  calls these "hash-locked, pinned-base" images — technically a floating tag
  can still be repointed upstream, so this is weaker than a true digest pin,
  though pinning to an explicit version (vs. `latest`) is itself a common and
  reasonable reading of "pinned." Not fixing without confirming which
  guarantee was actually intended.

## 10. Local demo & onboarding
- Status: clean (1 hardening suggestion, not exploitable — verified by attempted PoC)
- Reviewed `scripts/e2e_backend.py` (persistent-vs-disposable runtime dir
  handling, Alembic stamp-then-upgrade for older local demos, SPA fallback
  route) and `scripts/demo_service.py` (process management).
- **[investigated, not exploitable — no fix applied]** The local demo's SPA
  fallback handler (`spa_fallback`, `e2e_backend.py:114-119`) builds
  `frontend_dist / full_path` from the raw URL path and calls `.is_file()`
  with no `.resolve()` + ancestor check, unlike `LocalBlobStore.path_for`
  which does guard against traversal. This looked like a potential path-
  traversal read (e.g. serving `/etc/passwd` via `../../../etc/passwd` in the
  URL). Tested directly against the running local demo with both a raw
  literal `..` path and percent-encoded (`%2f`) variants over a raw TCP
  socket (bypassing curl's own URL normalization) — both were served
  `index.html`, not the target file; a `/assets/..%2f...` variant hit the
  `StaticFiles` mount's own traversal guard and 404'd. The ASGI layer
  (Starlette/uvicorn) evidently normalizes dot-segments in `scope["path"]`
  before the route handler ever sees `full_path`, so this isn't actually
  exploitable in practice. Still, the handler lacks defense-in-depth (no
  explicit resolve+ancestry check like the blob store has) — worth hardening
  to not rely on framework normalization alone, but not an active
  vulnerability, and this code path is local-demo-only (production serves the
  built frontend via nginx's own `try_files`, already correct per earlier
  session work).
- `demo_service.py`'s start/stop/restart/status process management and
  `start-dashboard.command`/`stop-dashboard.command` reviewed — no issues.

### Follow-up database/web audit — 21 July 2026

- The earlier process-management conclusion above was revised after reproducing
  a false-positive running state: the controller reported an existing PID while
  the recorded HTTP port refused connections.
- Confirmed cause: `_is_running()` checks only `os.kill(pid, 0)` and does not
  verify process identity, port ownership or `/health`. This is now tracked as
  a genuine local-launcher bug rather than a clean result.
- The database itself remained healthy: SQLite integrity and foreign-key checks
  passed, all blobs matched their SHA-256 values, stored snapshot totals tied to
  their lots/cash, and no orphan or duplicate publication/reconciliation rows
  were found.
- Full evidence and the verified web/API state are recorded in
  `docs/database-web-audit-2026-07-21.md`.

## 11. CI / quality gates
- Status: clean
- Reviewed `.github/workflows/ci.yml` in full: `test` (Postgres service +
  `check_tracked_sources.py` + hash-locked install + `pip-audit` + pytest),
  `frontend` (npm audit, OpenAPI drift check, unit tests, build, e2e),
  `containers` (both release images build + boot-check + nginx config
  syntax-check), `update-e2e-snapshots` (manual-only, correctly gated on
  `github.event_name == 'workflow_dispatch'`, direct-push-to-dispatched-branch
  is intentional per its own comment, not an oversight), and
  `dependency-review` (correctly PR-only). No logic bugs found — job
  triggers, `if:` guards, and permissions all match documented intent.

## 12. Holdings Excel distributions & FX — 22 July 2026

- **Fixed:** the holdings export previously showed `Недоступно` for the KZT
  row's USD-equivalent column. The exporter did not perform any conversion; it
  only copied native USD values for USD rows. It now derives KZT-to-USD using
  the report-date `report_fx_rate` carried by USD lots in the same OSIP
  workbook (KZT lots correctly carry a neutral rate of 1.0).
- The exporter now uses the National Bank of Kazakhstan's dated official
  USD/KZT RSS rate as its primary source for KZT/USD presentation conversions,
  recording the effective date and source method at the top of the workbook.
  If the NBK feed is unavailable, it transparently falls back to the
  consistent USD report rate carried by the OSIP workbook; if neither is
  available, the equivalent remains `Недоступно` rather than being fabricated.
  Dashboard carrying-value calculations remain unchanged and use the OSIP
  report FX field.
- **Changed:** the four allocation tables are now separate blocks on one
  `Распределения` sheet, each with a pie chart and an `Итого` row. The tables
  remain derived from the same ISIN-keyed filtered view and each weight total
  is validated.
- **Chart presentation:** native charts now use the reference workbook's
  spacious `15 × 7.5` layout, `varyColors`, legend placement by category
  count, and percentage-only labels with category/series names explicitly
  disabled. Anchors start below the frozen header so scrolling does not split
  or leave chart remnants behind.
