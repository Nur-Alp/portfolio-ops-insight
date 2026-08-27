# Database and web audit — 21 July 2026

## Scope

This audit verifies the persistent local Portfolio Operations Insight demo database and
the database-backed web/API projections served at `http://127.0.0.1:8765`.
The local demo uses SQLite under `.data/demo-service/runtime/`; it is not a
substitute for the required PostgreSQL 16 integration and recovery checks.

The audit was read-only. It did not delete, rewrite, approve or publish any
portfolio or multi-source dataset.

## Source load manifest

Eight real workbook files from `sources/` were recognized. Temporary `~$...`
files, `desktop.ini` and the DOCX note were intentionally skipped because they
are not importable workbook sources.

- OSIP own portfolio → `SOBSTV` snapshot
- OSIP TABYS portfolio → `TABYS` snapshot
- TABYS valuation workbook → valuation, holdings, cash/liabilities, NAV
  history, prices and inactive-evidence children
- TABYS unit-value history → `TABYS` active series and `SAQ` stale series
- Client dashboard → client accounts, trades, derivatives and opening dates
- Corporate-finance workbook → corporate-finance register
- Accounting budget workbook → validated landing/DQ evidence
- Accounting portfolio workbook → existing content-addressed upload; its
  existing accounting landing child was reused idempotently

Operational children were independently approved and published. The SAQ
series remains validated but unpublished by policy, and Accounting children
remain landing evidence rather than published Finance metrics.

## Verified database state

- SQLite `PRAGMA integrity_check`: `ok`.
- SQLite `PRAGMA foreign_key_check`: no violations.
- Alembic revision: `0007_multi_source_platform`.
- Seven immutable physical source uploads and seven matching blob files; every
  file's calculated SHA-256 matched `source_uploads.source_sha256`.
- Nine independently governed dataset versions: eight `published` and one
  accounting landing dataset in `validated` state.
- Three OSIP imports: two `published` and one deliberately `withdrawn`.
- Three portfolio snapshots, 49 position lots, 17 cash balances, 12 OSIP DQ
  issues, one multi-source DQ issue, three reconciliation results and 19 audit
  events.
- No orphaned source uploads, dataset versions, imports, snapshots, lots, cash
  rows, source rows, DQ records or audit records.
- No duplicate source hashes, published import versions, published dataset
  versions or reconciliation rules.
- No self-approved import/dataset and no published version without an
  independent reviewer.

For every stored OSIP snapshot:

- the snapshot position count equals the number of stored lots;
- stored purchase totals equal the sum of lot purchase amounts;
- stored derived carrying value equals the sum of lot carrying values;
- stored cash equals the sum of cash-balance rows; and
- derived carrying value plus cash equals the operational total.

All reconciliation differences above were exactly zero at stored decimal
precision.

## Publication and source behaviour

The default portfolio APIs expose the published SOBSTV and TABYS snapshots for
15 July 2026. The previously misassigned TABYS version for 16 July remains
`withdrawn`: it is retained as immutable evidence but does not appear in normal
published snapshot reads.

The published TABYS fund datasets use a 19 July 2026 business date. Therefore:

- `FUND-NAV-UNIT-SERIES` is `pass` with zero difference;
- `FUND-CASH` is `date_mismatch`; and
- `FUND-SECURITIES` is `date_mismatch`.

The two date mismatches are correct disclosure, not database corruption. The
application must not silently compare or merge the 15 July OSIP snapshot and
19 July fund valuation as though they shared a common reporting date.

## Import-handling hardening completed during this load

The source load exposed and corrected two long-term versioning edge cases:

- repeated source keys are retained as separate immutable records. If a
  workbook repeats a ticker or another natural key, the payload, formulas,
  cached value and source row are preserved while only the internal database
  key receives a deterministic row suffix;
- publishing a corrected child dataset for the same dataset type, scope and
  business date now flushes the previous version to `superseded` before the
  replacement is published. This works with the partial one-published-version
  constraint on both SQLite and PostgreSQL.

Regression tests cover both behaviours. These rules allow row additions,
reordering and repeated natural keys over future workbook revisions without
silently dropping source evidence.

## Web and API verification

The health endpoint returned `{"status":"ok"}`. All current SPA routes and the
principal database-backed APIs returned HTTP 200, including Management Centre,
Corporate Finance, Brokerage, Clients, Asset Management, Treasury, Operations,
Data Quality, Source Uploads, Reporting, Accounting, Risk and OSIP Portfolio.

Live API values were reconciled with the database for:

- published portfolio selection and report dates;
- SOBSTV overview position, purchase, carrying-value, cash and operational
  totals;
- TABYS fund valuation, holdings and unit history;
- brokerage source dates and summary counts;
- corporate-finance deal summary; and
- operations source readiness and reconciliation statuses.

The current automated verification baseline is:

- backend: 60 passed, one PostgreSQL-only check skipped locally;
- frontend: 23 passed; and
- browser workflow coverage: all route/workflow scenarios passed, including
  charts, language switching and the corrected mobile navigation assertion.

## Confirmed remaining bug

The local demo controller in `scripts/demo_service.py` treats `os.kill(pid, 0)`
as sufficient proof that the dashboard is running. It does not verify process
identity, the recorded port or `/health`. A stale PID file, PID reuse or a
process that is alive but no longer serving can therefore produce a false
“Demo is already running” result while the browser receives
`ERR_CONNECTION_REFUSED`.

Until this is fixed, `demo_service.py status` is advisory. A correct health
check must validate both the recorded process and an HTTP response from the
recorded port before reporting the demo as available. The controller should
remove only demonstrably stale state and must avoid signalling an unrelated
process after PID reuse.

## Intentional limitations, not bugs

- The accounting sources are landing/DQ evidence only; the current accounting
  child is validated but deliberately not published as Finance metrics.
- Risk and limits remain unavailable until an authoritative risk source is
  supplied.
- Source-reported fund NAV is not described as accounting-approved official
  NAV or official performance.
- This local audit does not prove production PostgreSQL concurrency, backup,
  recovery, OIDC, ingress or operational SLO readiness. Those remain governed
  by the production readiness checklist and UAT/reconciliation plan.
