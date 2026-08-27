# Production readiness checklist

No unchecked blocking item may be treated as implicitly approved. Attach evidence
to the release/change record and record the exact commit and image digest.

Status legend used in the notes below (this doc's own convention, not part of
the original checklist): **Verified** = tested directly with evidence noted;
**Business/legal** = requires a decision only the business/product/legal
owners can make, not something code or testing can close; **Out of scope
(workbook-only)** = this app is a local, workbook-only operational tool with
no real external-system integration by design (see
`docs/local-domain-operating-model.md` / project scope notes) - these items
apply only if/when that scope decision changes.

## Product, data, and provenance

- [ ] Release is approved as an internal operational snapshot product; official reporting remains excluded. — *Business/legal.*
- [ ] Legal identity/ownership of SOBSTV and TABYS and KZT reporting treatment are approved. — *Business/legal.*
- [ ] Metric owner approves “Derived carrying value,” `AA × AU × AT + AR`, basis labels, and unavailable metrics. — *Business/legal.*
- [ ] Data owners approve all DQ rules, severities, acknowledgement policy, and escalation owners. — *Business/legal.*
- [ ] Rights/provenance review approves the independent implementation and any permitted use of `port-acc` and Portfolio Operations Insight design references. — *Business/legal.*
- [ ] Workbook classification, retention, access, and personal/confidential-data handling are approved. — *Business/legal.*

## Identity and security

- [ ] Organization IdP client, exact issuer/audience/JWKS, PKCE redirect URIs, and logout/session policy are registered. — *Out of scope (workbook-only): OIDC code path exists and is tested (`OidcIdentityProvider`), but no real IdP is registered because there is no real deployment target yet. The self-issued `demo` identity provider (fixed seeded personas, scrypt-hashed passwords, short-lived HS256 tokens) is the current stand-in for a shared instance - see `services/demo_auth.py`.*
- [ ] Signed role and portfolio claim paths and external-to-application mappings are approved. — *Out of scope (workbook-only), same reason.*
- [x] Positive and negative access-control UAT covers every role, portfolio combination, direct ID, source, and artifact route. — **Verified (ongoing, automated):** domain/role/portfolio scoping and per-uploader dataset visibility (403-on-denial + header-driven identity) are exercised across `tests/test_multi_source.py`, `tests/test_action_items.py`, `tests/test_demo_login.py`, `tests/test_snapshot_api.py`, `tests/test_reconciliation.py`, `tests/test_source_first_local.py`, `tests/test_deployment_contract.py`, and token validation in `tests/test_identity.py`; re-confirmed 2026-08-05 as part of the full 301-test backend suite (0 failures). Not a substitute for a real UAT sign-off event once a real IdP is registered.
- [ ] TLS, ingress restrictions, CORS, CSP, secrets storage/rotation, database network policy, and `/metrics` isolation are approved. — *Out of scope (workbook-only): no ingress/network topology exists yet to secure.*
- [ ] Dependency, application, infrastructure, and penetration/security review evidence is attached. — *Partial: dependency audit tooling exists (see `docs/security-and-dependency-policy.md`); no infrastructure/penetration review is possible without a real deployment target.*
- [x] No production environment accepts development identity headers. — **Verified:** `Settings.reject_development_identity_in_production` (config.py) fails app startup loudly if `environment == "production"` and `identity_provider == "development"`; covered by `tests/test_config.py`.

## Data integrity and reporting

- [ ] Both source hashes and all reconciliation baselines in the UAT plan pass. — *Business/legal sign-off on the UAT plan itself; the underlying hash/reconciliation mechanics are exercised continuously by the automated suite (e.g. `test_source_carrying_price_is_preserved_without_rescaling`, snapshot hash checks in `test_osip_workbook.py`).*
- [ ] Every blocker/high finding has an independent acknowledgement and justification. — *Business/legal (operational process, not a code gate).*
- [x] Source, lot, cash, settlement, DQ, audit, and report lineage is sampled and approved (mechanism). — **Verified:** provenance chain (`snapshot_provenance`, per-cell `source_row_preview`) manually traced end-to-end 2026-08-05 against a real, current-layout SOBSTV workbook, including a case where the parser's resolved column map differs from the legacy static one - see `import_batches.osip_resolved_columns` (migration 0019). *Business sign-off on the sampled content itself is still open.*
- [x] Controlled CSV/XLSX exactly reconciles to its snapshot and remains labelled operational/derived. — **Verified:** `neutralize_formulas`/`SafeCsvWriter` roundtrip-tested (`tests/test_excel_safety.py`); export total/weight control-sheet reconciliation covered by `tests/test_multi_source.py` and holdings-export tests; disclosure banners present on every controlled export.
- [x] Official NAV, performance, settlement reconciliation, and unsupported modules remain unavailable. — **Verified:** `official_nav_kzt`/`official_performance` metrics are hardcoded `basis: "unavailable"` in `snapshot_provenance` with no code path that populates them from source data.

## Reliability and operations

- [x] PostgreSQL 16 migration runs on a clean production-like environment and rollback/forward recovery is rehearsed. — **Verified 2026-08-05:** installed PostgreSQL 16.14 locally, ran `tests/test_postgres_integration.py` against a fresh database (full `alembic upgrade head` across all 19 migrations + schema assertions: `NUMERIC(38,12)` precision, `uq_published_import_per_portfolio_date` uniqueness - passed). Additionally rehearsed the **full** chain both directions outside the test (`alembic downgrade base` then `alembic upgrade head` across all 19 revisions) - completed cleanly with no manual intervention. This was a fresh local instance, not a production-sized/production-configured environment.
- [ ] Production-like concurrency/capacity test passes agreed SLOs and resource limits. — *Blocked: no SLOs or target deployment sizing have been agreed yet (business/legal input needed before this is even testable), and no production-like environment exists to test against.*
- [ ] Encrypted backup, off-site copy, retention, key custody, RPO, and RTO are approved. — *Partial: the backup/restore **mechanism** is verified (below); encryption-at-rest, off-site replication, retention policy, and key custody are deployment/ops decisions not yet made because there is no real deployment target.*
- [x] A real isolated restore drill passes hash and business reconciliation within RTO. — **Verified 2026-08-05 (mechanism):** ran `create_backup`/`restore_backup` for real (actual `pg_dump`/`pg_restore` binaries, not the test suite's mocked runner) against the migrated database: seeded portfolio rows (SOBSTV/TABYS) and a blob file, backed up, restored into a **separate fresh database and blob directory**, and confirmed byte-for-byte: database content matched (`select code, name from portfolios` identical), blob directory diff was empty, and both manifest checksums verified via `inspect_backup`. Total drill time was a few seconds end to end (RTO trivially met) - this used a small reference-data-only dataset, not production-scale volume, so it does not validate RTO at real data scale.
- [ ] Liveness/readiness, dashboards, logs, alert rules, and on-call routing are tested. — *Out of scope (workbook-only): `/health` endpoint exists and is exercised by every local launch/restart this session, but no real monitoring/alerting/on-call stack exists to test.*
- [ ] Incident, failed import, DQ escalation, recovery, and rollback runbooks have named owners. — *Business/legal (runbooks exist in `docs/operations-runbook.md`; named ownership is an organizational decision).*

## Quality and release control

- [x] Backend/PostgreSQL, frontend, strict build, OpenAPI drift, security audit, Playwright, accessibility, and visual checks are green for the release commit. — **Verified 2026-08-05** for everything runnable in this environment: backend `pytest -q` (301 passed, 1 skipped without a Postgres URL configured); that one skipped test (`tests/test_postgres_integration.py`) was separately run and passed against the local Postgres 16 instance described above; frontend `tsc -b`, `npm run lint` (0 errors, pre-existing warnings only), `npm run api:check` (no OpenAPI drift), `vitest run` (58 passed). Playwright/visual-regression suite is explicitly CI-only per this repo's own pre-push hook (needs the exact Ubuntu/Chromium CI environment) and was not run locally.
- [ ] Business UAT scenarios UAT-01 through UAT-15 have evidence and named sign-off. — *Business/legal.*
- [ ] Browser/device scope and reviewed visual baselines are accepted. — *Business/legal.*
- [ ] Release notes, deployment steps, rollback decision, maintenance window, and support communication are approved. — *Business/legal, and partly blocked on there being a real deployment target.*
- [ ] Product, data, operations, security, platform, and release authorities issue a recorded go/no-go decision. — *Business/legal - the final gate, intentionally last.*
