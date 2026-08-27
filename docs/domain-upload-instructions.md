# Domain upload instructions

Use this guide when deciding which workbook or reference file to upload. The
application detects the feed from workbook structure; filenames are retained as
evidence and must not be used as the identity rule. Upload the complete source
workbook for one coherent reporting date, not a manually copied table.

## Quick rule

`Select domain → open Source uploads → select the approved workbook → review detected partitions and scope → inspect DQ/provenance → use the dashboard and exports.`

The intended operating model is multiple responsible operators per domain.
Each operator uploads their own source packages, checks the detected scope/date
and visible DQ/provenance warnings, and uses the charts and Excel exports. A
separate reviewer is not required for this source-first workflow. In a hosted
deployment, the user's OIDC domain claim should limit the domain and uploader
ownership should limit which source packages they can see.

## Visibility rule

Domain membership answers **where** a person may work; uploader ownership
answers **which workbooks** they may see. A normal domain operator may list,
download, compare, pin, chart, and export only datasets whose `uploader_id`
matches their actor identity. They must not see another operator's workbook,
source rows, DQ records, or derived charts merely because both operators share
the same domain or portfolio scope.

The application should keep prior versions for the uploader who created them,
and should select the latest eligible version from that same uploader. A
governance/admin role (the literal `"admin"` role on the actor) may be
granted cross-uploader access explicitly, via `_has_uploader_access` in
`routes/multi_source.py`; a broad domain claim (`domains: ["*"]`) alone still
does not provide it - the two are independent grants.

**Debugging tip:** an ad-hoc test request using a made-up `X-Actor-Id` can
return zero rows for a domain that actually has plenty of published data,
because that fake actor has no visibility into any real uploader's work -
this looks exactly like "no data exists" but means "this specific actor
can't see it." Before concluding a domain has no data, check what actor_id
the request used; the frontend's own development-mode default is
`"local-operator"` (`frontend/src/auth/session.ts`), not an arbitrary
string. When in doubt, a direct database query against `dataset_records`
gives unambiguous ground truth without the visibility rule in the way.

`local-operator` is also what every upload/review/publish action uses by
default now, not just reads - previously those were hardcoded to three
separate identities (`local-uploader`/`local-reviewer`/`local-publisher`)
distinct from the read default (`dashboard-reader`), so an operator's own
upload was never visible to their own very next read in a fresh local
setup. One identity for the whole workflow matches the actual local
operating model: one person doing everything for their domain, not four
simulated coworkers.

## Reprocessing already-published data after a parser/logic fix

Fixing a bug in ingestion (a parser, a derived-field calculation like
`_risk_utilization`) never retroactively changes data that's already been
published - the wrong output was computed once at ingestion time and stored
verbatim in `dataset_records.payload`. Every already-published dataset
keeps serving the old, wrong value forever until it's explicitly
re-imported and re-published.

This has two consequences worth remembering:

- **Fix the code, then also fix the data.** After any ingestion/computation
  bugfix, re-import and re-publish every already-published dataset that
  used the old logic - in every environment that has one, not just whichever
  one you happened to test against. A local demo/scratch deployment and the
  real persistent local dashboard (see `docs/demo-deployment.md`) are
  separate databases with independently-uploaded copies of the same source
  files; fixing one does nothing to the other.
- **Multiple uploads compound this.** Because of the per-uploader visibility
  rule above, the same source file can be uploaded (and independently
  published) under several different `uploader_id`s over time - each one
  needs its own re-import, not just the one you last tested with.

## Upload matrix

| Domain role | Upload this | Detected source / destination | Scope to confirm | What it feeds |
|---|---|---|---|---|
| Back Office — OSIP owner | OSIP own-portfolio `.xls` | `osip_portfolio` → controlled OSIP import | `SOBSTV` | Overview, holdings, cash/calendar, operations and OSIP exports |
| Back Office — OSIP owner | OSIP TABYS-portfolio `.xls` | `osip_portfolio` → controlled OSIP import | `TABYS` | TABYS OSIP snapshot, holdings, cash/calendar and exports |
| Asset Management | TABYS valuation/holdings workbook `.xlsx` | `tabys_valuation` → multi-source datasets | `TABYS` | Asset-management valuation, holdings, cash/liabilities, NAV history and prices |
| Asset Management | TABYS or SAQ unit-value history `.xlsx` | `fund_unit_history` → unit-history datasets | `TABYS` or `SAQ` | Unit-value history and comparison; confirm whether SAQ is active or stale |
| Treasury | OSIP portfolio workbook `.xls` | `osip_portfolio` → OSIP snapshot | `SOBSTV` or `TABYS` | Treasury cash/calendar and portfolio cash controls; Treasury is currently a Back Office view |
| Risk manager | SOBSTV risk-limits workbook `.xlsx` | `risk_limits_sobstv` → Risk and limits | `SOBSTV` | Country, currency, FX position, issuer, sector, instrument, duration and IFRS limit controls |
| Risk manager | TABYS risk-limits workbook `.xlsx` | `risk_limits_tabys` → Risk and limits | `TABYS` | TABYS limit controls and status charts |
| Accounting | Accounting statements workbook `.xlsx` | `accounting_statements` → balance sheet and income statement | `ACCOUNTING` | Accounting landing/DQ evidence; not official accounting results until approved source policy allows it |
| Accounting | Accounting budget workbook `.xlsx` | `accounting_budget_landing` → landing plus budget detail | `ACCOUNTING` | Budget landing evidence and budget detail/DQ |
| Accounting | Accounting portfolio workbook `.xls`/`.xlsx` | `accounting_portfolio_landing` → landing plus portfolio detail | `ACCOUNTING` | Portfolio-detail landing evidence and DQ; preserve formula/date warnings |
| Client Operations / Brokerage | Client/brokerage workbook `.xlsx` | `client_brokerage` → clients, trades, derivatives, opening dates and detected calendar partitions | `BROKERAGE` | Brokerage, Clients and related operational pages |
| Corporate Finance | Corporate-finance workbook `.xlsx` | `corporate_finance` → corporate-finance register | `CORPFIN` | Mandates, deals, fees and corporate-finance controls |

## Shared reference files

These are not portfolio/domain workbooks. They are controlled reference
artifacts and should be uploaded from the Imports page by an authorized
uploader.

| Reference artifact | Upload panel | Accepted format | Used by | Required handling |
|---|---|---|---|---|
| Bloomberg dividend dictionary | `Словарь дивидендов Bloomberg` | `.xlsx` | Holdings HPR and expected dividend cash flows | Replace the active version only with a dated/current extract. Review source date, latest ex/pay dates, future payments and freshness warning. Future pay dates are excluded from HPR until paid. |
| Classes and ratings dictionary | `Словарь классов и рейтингов` | `.csv`, `.xlsx`, or `.xls` | OSIP classification, risk buckets and charts | Required columns: `ISIN`, `Класс актива`, `Class`, `Rating group`, `Focus/sector/factor`. Review changed/added/removed ISINs because the replacement affects every portfolio view. |

The classes/ratings dictionary currently has a packaged default and a runtime
override. The upload replaces the active runtime version; it does not rewrite
the tracked default in the repository. The Bloomberg upload similarly replaces
the active runtime dividend file and records its SHA-256 and freshness status.

## What not to upload

- Do not upload a screenshot, PDF, manually filtered extract, or a workbook
  with deleted/relabelled source columns in place of the approved source.
- Do not upload temporary Excel lock files beginning with `~$`.
- Do not assign an OSIP portfolio from the filename or from overlapping ISINs;
  select `SOBSTV` or `TABYS` explicitly.
- Do not upload a dividend dictionary as a normal domain dataset, or a classes
  dictionary as an accounting/risk workbook. Use the dedicated reference-data
  panels.
- Do not use a new workbook revision until the detected partitions, report date,
  business date, source version, and DQ findings have been reviewed.

## Minimum review after every upload

1. Confirm the detected source type and selected scope.
2. Confirm the workbook/report date and business date independently; a date in
   the filename is only a warning signal.
3. Review sheet/partition mapping and the first/last source rows.
4. Check DQ findings, missing fields, formula errors, and date mismatches. For
   `.xlsx`, the application separately checks formula cells that actually back
   published fields: an empty or error cached result blocks publication. Errors
   in unused helper/template cells remain visible as evidence but do not block
   a valid dataset. For legacy `.xls`, cached formula-result validation is not
   exposed by the reader; the dashboard uses the saved source values and marks
   that limitation explicitly.
5. Confirm the source filename, SHA-256, parser version, and version number are
   visible in the registry.
6. For a replacement, compare it with the previous version before publishing.
7. Verify the domain page and export show the new version and expected source
   date. Keep the older version available for comparison; do not overwrite it.

## Default domain-owner permissions

For the normal domain-operator workflow, the practical minimum is:

| Permission | Use |
|---|---|
| `reader` | Read the domain page, source status, provenance, charts and exports |
| `uploader` | Upload the domain's approved workbooks and reference artifacts |

The same person may hold both permissions. After upload, the operator reviews
the detected partitions, dates, DQ findings, freshness, and source references;
the application keeps the prior version and does not silently overwrite it.
The ownership filter applies to every dataset list, source download, detail
drawer, comparison, domain chart, and Excel export.

## Optional hosted controls

| Permission | Intended use |
|---|---|
| `reader` | Read status, provenance, published datasets and exports |
| `uploader` | Upload the role's approved workbooks/reference artifacts |
| `reviewer` | Review mappings, DQ and source totals; approve a different user's upload |
| `publisher` | Publish the reviewed version or withdraw a mistaken published version |

`reviewer` and `publisher` are optional additions for a later shared,
regulated, or downstream-writing deployment. They should not block the normal
domain owner's ability to inspect the source-backed dashboard and create
exports. Reference artifacts remain shared controls: in a hosted setup, limit
replacement to a designated Back Office/Risk or data-governance owner and add
independent review only when policy requires it.
