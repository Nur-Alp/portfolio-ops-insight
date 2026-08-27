# Business UAT and reconciliation plan

This document is the executable acceptance script for the first release: an
internal OSIP portfolio snapshot and operations dashboard. It is not acceptance
for official NAV, performance, accounting, trading, compliance, or client reporting.

## Test record

| Field | Value |
|---|---|
| Release commit / image digest | _Required_ |
| Environment and URL | _Required_ |
| PostgreSQL / browser versions | _Required_ |
| SOBSTV source SHA-256 | `b9d028306add94c50d2675d5bb7a91335a0ce113ba08b3c01f6184ccb4cefe27` |
| TABYS source SHA-256 | `2dc88c9ab0cdfb6de04eeb804bdeb63b154265e734670c6f6f612ea60629ff0e` |
| Tester / date | _Required_ |

## Reconciliation baseline

All financial comparisons use Decimal values. Display rounding does not replace
exact API/export reconciliation.

| Portfolio | Current lots | Unique ISINs | Raw / unique settlements | Purchase KZT | Derived carrying KZT | Cash KZT | Derived operational KZT |
|---|---:|---:|---:|---:|---:|---:|---:|
| SOBSTV | 19 | 15 | 10 / 5 | 4,695,258,648.74 | 4,774,363,156.14 | 42,009,877.85 | 4,816,373,033.99 |
| TABYS | 15 | 12 | 0 / 0 | 52,103,596.35 | 63,779,568.02 | 416,640.61 | 64,196,208.63 |

The value called **Derived carrying value** is `AA × AU × AT + AR`. It must
always be labelled derived and must never be renamed NAV, market value, or profit.

## UAT scenarios

Record Pass/Fail, evidence link, tester, and defect ID for every scenario.

| ID | Action and expected result | Required owner | Result / evidence |
|---|---|---|---|
| UAT-01 | Upload each exact workbook. The SHA, portfolio, 15 July 2026 report date, row counts, and totals match the baseline. | Data owner | _Required_ |
| UAT-02 | Upload the same bytes again. The API returns the existing import and no second version, snapshot, or blob is created. | Operations | _Required_ |
| UAT-03 | Upload an approved corrected file. It becomes a new immutable version; publishing it supersedes only the older same-portfolio/date version. | Operations | _Required_ |
| UAT-04 | Insert/reorder business rows without changing columns. Counts/totals remain stable. Change a required header and confirm rejection. | Data owner | _Required_ |
| UAT-05 | Confirm 10 SOBSTV raw settlement rows become five events with two source references each; the 14 July event is overdue. No settlement total is implied. | Operations | _Required_ |
| UAT-06 | Open KPI basis labels, an aggregated holding, its individual lots, DQ evidence, and raw source references. Every aggregate remains traceable. | Product owner | _Required_ |
| UAT-07 | Confirm formula-error/blank workbook outputs are unavailable, not zero. Official NAV and performance stay visibly unavailable on screen and in CSV. | Data owner | _Required_ |
| UAT-08 | Attempt uploader self-approval and incomplete blocker/high acknowledgement. Both fail. Independent review with justification succeeds, then publisher publication succeeds. | Control owner | _Required_ |
| UAT-09 | Publish SOBSTV and TABYS independently. Combined portfolio metadata exposes different report dates if they differ. | Operations | _Required_ |
| UAT-10 | Generate CSV. Reconcile summary to lots plus cash exactly; verify holdings, cash, settlements, calendar, DQ, source hash, reviewer, publisher, version, and disclosures. A repeat run is byte-identical. | Reporting owner | _Required_ |
| UAT-11 | Test uploader/reviewer/publisher/reader IdP groups and SOBSTV-only, TABYS-only, both, and no-portfolio users. API list and direct-ID access must agree; UI hiding alone is insufficient. | Security owner | _Required_ |
| UAT-12 | Validate desktop/mobile navigation, URL filters, evidence drawers, keyboard use, focus, contrast, loading/error/empty states, and reviewed visual references. | Product / accessibility | _Required_ |
| UAT-13 | Run approved concurrent uploads/reads at production-like volume. No duplicate versions, timeouts, precision drift, or lost audit events; agreed SLOs pass. | Platform owner | _Required_ |
| UAT-14 | Restore a recent encrypted backup into isolation. Reconcile DB/blob hashes and all business counts, retrieve both originals, and meet approved RPO/RTO. | Platform / data owner | _Required_ |
| UAT-15 | Trigger readiness, error-rate, latency, and service-down alerts. Correct on-call route receives them and follows the runbook. | Operations owner | _Required_ |

## Engineering prechecks

These checks reduce manual repetition but do not fill the owner/evidence column
above and do not constitute business, identity, platform, or release approval.

| UAT scope | Automated precheck |
|---|---|
| UAT-01–UAT-10 | Parser/API golden suites and the live Playwright workbook-to-export journey |
| UAT-09 | Positive unequal-report-date API test, in addition to independent publication |
| UAT-10 | Repeat report generation returns the same report ID, SHA-256, and exact bytes |
| UAT-11 | Signed-token issuer/audience/expiry/role/portfolio negatives and direct source/snapshot/report-artifact authorization tests |
| UAT-12 | Six-route desktop browser, keyboard/accessibility, evidence-drawer, mobile-shell, and visual-baseline suite |
| UAT-13 | `scripts/capacity_probe.py`; local tool validation is not production-like evidence |
| UAT-14 | Verified backup/restore primitives and `scripts/reconcile_recovery.py`; a real isolated encrypted restore is still mandatory |
| UAT-15 | Prometheus alert definitions and runbook; target routing must still be triggered and observed |

## Sign-off

Sign-off means the evidence above was reviewed, not merely that automated tests passed.

| Accountability | Named person | Decision / date | Conditions or evidence |
|---|---|---|---|
| Product owner | _Required_ | _Required_ | |
| Portfolio/data owner — SOBSTV | _Required_ | _Required_ | |
| Portfolio/data owner — TABYS | _Required_ | _Required_ | |
| Operations/control owner | _Required_ | _Required_ | |
| Security/identity owner | _Required_ | _Required_ | |
| Platform/on-call owner | _Required_ | _Required_ | |
| Release authority | _Required_ | _Required_ | |
