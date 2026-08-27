# UAT execution record — 21 July 2026

This is the engineering execution record for the controlled local UAT pass. It
uses a fresh disposable SQLite runtime and the real workbooks in `sources/`.
The local deployment is source-authoritative: content DQ findings are retained
as warnings and do not block a successfully parsed workbook. This is not a
business-owner sign-off and does not approve official NAV, performance,
accounting or risk reporting.

## Environment

| Item | Result |
|---|---|
| Demo URL | `http://127.0.0.1:8765` |
| Database | Fresh disposable SQLite runtime; no prior versions carried into the check |
| Source files loaded | 8 real workbooks; lock files, `desktop.ini` and DOCX rejected |
| Source detection | Content/header based; filenames retained as evidence only |
| Backend tests | 73 passed, 1 skipped |
| Frontend tests | 24 passed |
| OpenAPI check | Passed |
| Frontend production build | Passed; rebuilt `frontend/dist` |
| Browser automation | Unavailable in this environment; the UI calls were exercised through the same HTTP contracts and this limitation remains open for owner UAT |

The persistent local demo was also smoke-tested after the fresh pass: the
service reported `http://127.0.0.1:8765` running, `/health`, `/`, and
`/api/v1/operations/source-readiness` each returned HTTP 200. Its readiness
registry contains 17 published non-OSIP child datasets plus the two published
OSIP portfolio snapshots (19 child/snapshot views in total). The published
OSIP portfolio list reports SOBSTV and TABYS at 20 July 2026.

## Upload and publication results

| Domain | Workbook(s) | Child datasets | Result |
|---|---|---:|---|
| Back Office | Two OSIP `.xls` files | 2 portfolio snapshots | Explicitly assigned, structurally parsed and source-first published; DQ-04/DQ-05 remain visible warnings |
| Back Office | TABYS valuation `.xlsx` | 6 | Detected and source-first published; valuation, holdings, cash/liabilities, NAV history, prices and evidence-only partitions are separate |
| Back Office | TABYS unit history `.xlsx` | 2 | TABYS and SAQ source series published; SAQ is explicitly inactive/non-current |
| Client Operations | `Клиентский_дашборд.xlsx` | 6 | Client, trade, derivative, opening-date, maturity and dashboard children published |
| Corporate Finance | `Направление_Корпфин_01072026.xlsx` | 1 | Seven-deal register published with source text and DQ |
| Accounting landing | Two accounting workbooks | 2 | Stored and visible as landing/DQ evidence only; no accounting metrics |

## Domain totals verified

### Back Office

* SOBSTV: 19 lots, 15 ISINs, purchase `4,695,258,648.74219` KZT,
  carrying `4,784,765,279.9467931433` KZT, cash `39,405,543.2353` KZT.
* TABYS OSIP: 15 lots, 12 ISINs, purchase `52,103,596.35397676` KZT,
  carrying `63,573,512.023840000738` KZT, cash `417,484.7614` KZT.
* TABYS valuation: securities `63,573,512.02384` KZT, cash
  `417,484.75999999995` KZT, liabilities `98,179.76999999999` KZT, reported
  NAV `63,892,817.01383989` KZT, units `105.06954000000013`, unit value
  `608,100.28304911` KZT. The NAV tie-out residual is `-0.00000010996` KZT;
  the OSIP/valuation cash difference is `0.00140000005` KZT, both within the
  configured 1 KZT tolerance.

### Client Operations

* 197 clients and 202 positions from the account snapshot.
* 8,732 trades; 428 derivatives.
* 108 maturity events, total `67,900,277,081` KZT, nearest date 15 July 2026,
  latest date 15 April 2035.
* The clean source parse excludes subtotal/grand-total rows; no
  `Предстоящие расчёты` rows are used.

### Corporate Finance

* 7 deals, 2 explicitly active, period `1H2026`.
* ISIN sets are normalized while the original deal text is retained.
* Currency-specific values are kept separate; ambiguous amounts are not
  guessed or charted.

## Observed DQ (non-blocking in local source-authoritative mode)

These findings are not repaired or hidden. They remain linked to the exact
workbook evidence so an owner can annotate them, but none prevents the local
domain view or an operational export. A future hosted deployment may choose to
turn the same rules back into publication gates.

For this local source-authoritative rollout, the engineering disposition is
therefore to preserve each supplied value or absence exactly, label the
limitation, and avoid an invented correction. “Resolved” here means that the
workflow has a documented treatment; it does not mean that the workbook was
edited or that an unavailable value was inferred.

| Dataset / code | Severity | Evidence | Optional owner note |
|---|---|---|---|
| `client_dashboard_snapshot` / `CLIENT-DASH-01` | Medium | Dashboard total assets `98,849,584,296.374767336` KZT vs `Лист4` register `98,837,071,968.86491` KZT; difference `12,512,327.509857336` KZT. Both source values remain visible. | Record which source the owner uses for decisions; no automatic correction is made. |
| `fund_prices` / `TABYS-PRICE-01` | High | 8 holdings have no price in the valuation workbook. | Leave unavailable if the supplied workbook is the authoritative source. |
| `fund_prices` / `TABYS-PRICE-02` | Medium | Latest price date is 17 July 2026 while the valuation report is 19 July 2026. | Display the source date mismatch; do not shift or fabricate a price date. |
| `fund_unit_series` / `UNIT-03` | High | SAQ latest observation is 19 January 2025; series is explicitly inactive. | Keep it historical/non-current; it is not used for current TABYS metrics. |
| `fund_unit_series` / `UNIT-01/02/04/06` | Medium/high | Duplicate/out-of-order dates, 2 missing TABYS values, and external references remain in the workbook. | Preserve missing values and source references; parser does not repair evidence. |
| `corporate_finance_register` / `CORPFIN-01` | Medium | At least one amount/unit is ambiguous in the source text. | Keep the amount unavailable rather than guessing its unit. |
| `corporate_finance_register` / `CORPFIN-03` | Medium | Commission rate is absent. | Keep the rate unavailable; do not derive it from unrelated fields. |
| `client_open_dates` / `CLIENT-02/03/04` | Medium/high | 245 unmatched and 1 ambiguous opening-date references; exact matching is intentionally used. | Keep unresolved rows visible; opening dates remain unavailable where the source cannot prove a match. |

### Disposition of the four owner-review items

| Item | Local treatment | What remains for owner UAT |
|---|---|---|
| Client dashboard vs `Лист4` total | Keep both source totals and show the difference; neither is silently replaced. | Confirm which view the owner uses for operational decisions. |
| TABYS missing/stale prices | Keep missing prices unavailable and retain the 17 July source date; no price is backfilled. | Confirm the warning and date label are understandable. |
| SAQ history | Publish as historical source evidence but mark inactive/non-current; it is excluded from current TABYS metrics. | Confirm that the historical series is not mistaken for a current portfolio. |
| Corporate Finance demand/commission | Preserve raw text; leave ambiguous demand/amount and absent commission unavailable. | Confirm that the register is useful without guessing those fields. |

## UAT status

The engineering portion is ready for a short owner-led UAT. A named person for
each domain should open the local app and record whether the source-backed
presentation is usable; this is a usability and interpretation check, not a
requirement to repair or approve the supplied workbooks:

1. Back Office checks OSIP/valuation totals, date labels, missing-price rows and
   the TABYS NAV/unit tie-out.
2. Client Operations checks client/position/trade/derivative counts, the
   maturity calendar and the dashboard-vs-`Лист4` discrepancy.
3. Corporate Finance checks all seven deals, ISINs, currencies, active flags and
   the two ambiguous/missing values.

## Owner sign-off and correction log

Complete one row per responsible person during the local walkthrough. Attach a
screen capture or exported workbook when a correction is found; do not edit the
source workbook to make the dashboard pass.

| Domain owner | Person / date | Scenarios checked | Result | Correction or decision | Follow-up issue |
|---|---|---|---|---|---|
| Back Office | _Required_ | OSIP totals; TABYS valuation; prices; NAV/unit tie-out; exports | _Pending_ | _Required_ | _Required_ |
| Client Operations | _Required_ | clients; positions; trades; derivatives; maturity; `Лист4` discrepancy | _Pending_ | _Required_ | _Required_ |
| Corporate Finance | _Required_ | 7 deals; ISINs; currencies; active flags; demand/commission | _Pending_ | _Required_ | _Required_ |

Until these three rows are completed, the application is controlled local UAT,
not a signed-off operational release. The rows are not publication blockers in
the local source-authoritative deployment.

Accounting and Risk remain source-pending placeholders. They should not be
turned into metric pages until the promised authoritative files and metric
definitions arrive.
