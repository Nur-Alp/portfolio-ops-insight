# Risk and Accounting — implementation status and remaining contracts

This document supersedes the original Phase 2 groundwork note. It is an
implementation-status record, not a claim that the platform publishes
official accounting or risk reporting.

## Implemented platform capabilities

### Risk

- Normalized SOBSTV and TABYS limit controls, source-authoritative status,
  utilization, near-breach classification, and immutable source-cell links.
- Breach/near-breach watchlist, dimension/detail drilldowns, duration controls,
  country/instrument pivot, and action-item workflow.
- Version comparison, published-version breach/near-breach trend, and
  dimension-specific top-concentration charts.
- Controlled Excel export, standard pagination, uploader/domain isolation,
  and unavailable-state disclosure.
- Near-breach policy is configured with `OSIP_RISK_NEAR_BREACH_THRESHOLD`
  (default `0.90`) and recorded with the policy version
  `OSIP_RISK_NEAR_BREACH_POLICY_VERSION` (default
  `utilization-ratio-v1`) in parsed records and summaries.

### Accounting

- Source-readiness cockpit, statement, budget, and portfolio-detail tables;
  all retain immutable source-cell evidence.
- Source current/prior and quarter/YTD columns, dataset-version comparison,
  and account-code drift/new-code registry.
- Accounting portfolio to explicitly selected OSIP portfolio reconciliation,
  including pass/fail/date-mismatch evidence.
- Formula/external-link audit for `.xlsx`, explicit legacy `.xls` limitation,
  and a publication gate that blocks an `.xlsx` when a formula backing a
  published field has an empty or erroneous saved result.
- Controlled Excel export, action-item workflow, source/date disclosures, and
  uploader/domain isolation.

## Guardrails

1. The dashboard reads saved source values; it does not claim to recalculate
   arbitrary Excel formulas.
2. Workbook-wide helper/template formula errors are retained as evidence but
   do not block publication unless they back a parsed/published field.
3. `.xls` values remain usable, but formula/cached-result pairs cannot be
   independently inspected by the reader. Audit-only `.xlsx` conversions are
   for review and are never substituted for original source inputs.
4. Risk concentration is selected within one dimension at a time. Country,
   issuer, sector, and other overlapping dimensions must not be summed into a
   single exposure total.
5. Accounting budget/actual and period comparisons use only source-provided
   periods and line codes. The platform does not infer missing periods or
   silently map unrelated accounts.

## Remaining product decisions before adding new metrics

| Area | Decision required |
|---|---|
| Accounting budget vs actual | Approve the mapping of budget lines to accounting line codes, units, period cut-off, and treatment of restatements. |
| Account mapping overrides | The current registry uses source line code as durable identity. Decide whether Accounting needs a governed override dictionary for merges/renames across structurally different packs. |
| Risk threshold policy | Decide ownership and change process for threshold/policy-version configuration; the platform already records both values. |
| Accounting formula policy | Decide whether future authoritative accounting `.xls` inputs stay accepted with the explicit limitation or must be supplied as `.xlsx`. |
| Production operation | Provision OIDC, PostgreSQL, immutable object storage, backup/restore monitoring, and explicit HTTPS CORS origins. These are environment actions, not local feature toggles. |

## UAT minimum scenarios

- Risk: OK, near-breach, breach, not-applicable, unavailable, added/removed
  version rows, and a historical trend.
- Accounting: changed/new account code, statement version difference, budget
  line without approved mapping, reconciliation pass/fail/date mismatch.
- Formula safety: valid saved result, blank saved result, cached error, unused
  helper-cell error, and legacy `.xls` unavailable status.
- Access: a domain operator can only access their own uploads, source rows,
  comparisons, charts, and exports.
