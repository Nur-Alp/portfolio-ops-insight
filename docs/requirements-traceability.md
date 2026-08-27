# Reference requirements traceability

This matrix maps the acceptance section of the feasibility/delivery reference to
current authoritative evidence. “Verified” means current code plus a covering test;
it does not replace the organization sign-offs in the UAT plan.

## Data acceptance

| Requirement | Status | Evidence |
|---|---|---|
| 19 SOBSTV and 15 TABYS current lots; 15 and 12 portfolio ISINs; repeated lots retained | Verified | `tests/test_osip_workbook.py`, `tests/test_snapshot_api.py` |
| 10 raw SOBSTV settlements become five with duplicate lineage | Verified | Parser/API golden tests and settlement source links |
| 14 July event is overdue on 15 July report | Verified | Parser and calendar API tests |
| Derived carrying, cash, and operational totals reproduce with Decimal | Verified | Golden parser/API tests and CSV reconciliation test |
| Broken formulas/blanks never become zero | Verified | DQ-01, unavailable fields, metric basis tests |
| Identical hash is idempotent | Verified | Import service and API/browser idempotency tests |
| Layout tolerates row insertion/reordering and rejects changed columns | Verified | Parser contract tests |
| Golden real uploads and sanitized fixture | Verified | Two repository `.xls` files plus `tests/fixtures/sanitized_osip_rows.json` |

## Product acceptance

| Requirement | Status | Evidence |
|---|---|---|
| KPIs disclose source/formula basis, date, version, DQ/publication state | Verified | Metric definitions, overview/readiness APIs, Overview/Reporting pages |
| Aggregates drill to lots and raw rows | Verified | Instrument aggregation, lot/DQ drawers, live browser tests |
| Filters/totals agree across cards, allocations, tables, and export | Verified in engineering; business UAT pending | API reconciliation and controlled CSV tests; UAT-06/UAT-10 |
| Unsupported metrics are visibly unavailable | Verified | Governed disabled metrics, UI badges, CSV unavailable rows |
| Critical DQ blocks approval/export without acknowledgement in controlled workflow | Verified; local source-first mode intentionally relaxes this gate | Workflow/API tests plus `tests/test_source_first_local.py` |
| Published exports retain version and approval identity | Verified | `ReportRun`, CSV metadata, audit event, artifact tests |
| Role and portfolio access is enforced by API | Verified in engineering; IdP UAT pending | OIDC issuer/audience/expiry/role/portfolio tests plus import, source, snapshot, and report-artifact direct-object tests; UAT-11 |

## Engineering acceptance

| Requirement | Status | Evidence |
|---|---|---|
| Applicable `port-acc` tests remain passing | Not applicable by approved architecture | No `port-acc` source/table/demo reuse; independent model at repository root |
| API, generated-client drift, integration, E2E, accessibility, visual, calculation, parser, and release-image suites in CI | Verified | `.github/workflows/ci.yml`, OpenAPI generator, pytest/Vitest/Playwright/deployment suites |
| PostgreSQL constraints, precision, FKs, and published uniqueness | Verified | Migration and PostgreSQL integration tests |
| Migrations reversible or forward-recoverable | Verified for baseline | Upgrade/schema-diff/downgrade tests and recovery runbook |
| Originals and audit evidence immutable and recoverable | Engineering verified; real drill pending | Hash blob store, source retrieval, workflow tests, backup/restore tests, deterministic pre/post recovery reconciliation; UAT-14 |
| Dependencies locked and security-reviewed | Verified continuously | `requirements.lock`, npm lock, CI audits/dependency review |
| Production operations and identity controls | Engineering verified; external configuration pending | Non-root release images and deployment runbook, CSP/security-header ingress with private metrics, health/metrics/alerts, threshold-enforcing capacity probe, OIDC/PKCE, production checklist |

## Remaining controlled/production release blockers

These items apply to a hosted or controlled four-eyes release. They do not
prevent the current single-owner, source-authoritative local UAT described in
`docs/local-domain-operating-model.md` and `docs/uat-execution-2026-07-21.md`.

1. Provenance/design/code-rights approval.
2. Organization IdP registration, final claim/group mapping, session policy, and access UAT.
3. Production-like concurrency/capacity test with agreed SLOs.
4. Real encrypted backup/restore drill plus approved RPO/RTO/retention/key custody.
5. Named business, data, operations, security, platform, and release-owner sign-off.
