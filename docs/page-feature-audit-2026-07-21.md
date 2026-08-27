# Page and feature audit — 21 July 2026

## Scope and decision standard

This review covers the routes, widgets, controls, charts, drawers, exports and
workflow actions currently present in the frontend and their backing API
endpoints. It uses the current operating model: one person runs the application
locally for one business domain and supplies the workbooks for that domain.

Each feature is classified as:

- **Keep** — directly helps the domain owner do the job and is backed by a
  supplied source or a clearly documented derivation.
- **Keep, but clarify** — useful, but the current label, scope or interaction
  can mislead the operator.
- **Reduce or remove** — duplicates another control, creates ceremony without
  operational value, or is not useful with the current data volume.
- **Not available yet** — correctly visible as unavailable because the source
  or method is absent.

## Executive conclusion

The application has a solid source-to-view foundation, but the current shell
still looks like a multi-tenant controlled platform while the actual product is
a local domain workbench. The next work should focus on removing misleading
controls and making the source-backed workflows obvious, not adding more KPI
cards.

The highest-priority findings are:

1. The global **Currency** selector is displayed on legacy pages but does not
   change the overview, cash, allocation or holdings API values. It is a false
   control and should either be implemented end-to-end or removed.
2. The local top bar displays **Read**, while upload and workflow buttons use
   hard-coded `local-uploader`, `local-reviewer` and `local-publisher` actors in
   the API client. This is confusing and makes the visible role inaccurate.
   Local mode needs one explicit **Domain operator** identity, or the role pill
   must be presented as a technical compatibility detail.
3. Source-first non-OSIP datasets are immediately readable, but **My work**,
   DQ banners and upload copy still imply mandatory review/publication steps.
   These should become source warnings and optional notes in local mode.
4. **Management centre** and **Operations and reconciliations** currently use
   the same read model and nearly the same page. One should become the concise
   cross-domain landing page and the other the detailed readiness/reconciliation
   view.
5. Brokerage/client/corporate-finance tables are capped at 250/12 rows with no
   pagination or domain filters. This is not safe as workbook volumes grow.
6. The client page already shows account/IIN fields in its main table, while its
   detail subtitle says identifiers are only available in the detail view. The
   copy is contradictory and should be corrected for local mode.
7. The DQ table column labelled **Confirmation** currently displays the number
   of source references, not a confirmation value. Rename it to **Source
   evidence** or show the actual acknowledgement status.

## Shared shell and navigation

| Feature | Assessment | Decision |
|---|---|---|
| Domain selector | Correctly changes the local workspace and request domain header. `*` exposes all domains, which is useful for a lead operator but should not be the implied default for a single-domain launcher. | **Keep, clarify**. Make the configured domain the launcher default and label `*` as **All domains**. |
| Role pill | Always renders `Read`, although uploads/actions use explicit local actors with uploader/reviewer/publisher roles. | **Change**. Show **Domain operator** in local mode; retain technical roles for API tests/hosted mode only. |
| RU/EN switch | Works as a session-only UI preference. Source workbook evidence remains unchanged. | **Keep**. |
| Environment pill | Correctly discloses operational/derived data. | **Keep**. |
| Portfolio/report-date/basis/currency filter bar | Portfolio, snapshot and basis are useful on OSIP pages. Currency is currently not propagated consistently. | **Keep portfolio/snapshot/basis; fix or remove currency**. Scope the bar to OSIP pages and show which pages each filter affects. |
| Command palette | Navigation search and OSIP instrument lookup work. It does not search clients, trades, deals, datasets or DQ findings despite its generic search wording. | **Keep, narrow or extend**. Call it **Search portfolio data** only on OSIP pages, or add domain-aware search. |
| Sidebar groups | The navigation is long but scrollable and domain filtering is useful. Legacy OSIP routes are mixed with the newer domain routes. | **Keep, reorganize**. Put OSIP under Back office/Treasury and hide legacy duplicates unless needed. |
| Footer disclosure | Correctly states the operational nature of the data. | **Keep**. |

## Route-by-route audit

### `/my-work` — My work

**Useful:** a single landing page for the selected domain, failed parsing notices,
stale-source warnings, and a short list of recently published versions.

**Currently misleading:** `Awaiting review`, `Ready to publish`, and `DQ
blockers` imply that a local domain owner must complete a hosted workflow. In
source-first mode, non-OSIP children are already published and readable. The
notification text still says to acknowledge or remediate blockers.

**Recommendation:** keep the page, but make it a **Source health** queue in local
mode. Show failed imports, stale dates, schema changes, source mismatches and
unavailable metrics. Keep approval/publish task cards only for explicit OSIP
controlled imports or a future hosted mode.

### `/management` — Management centre

**Useful:** a compact cross-domain status landing page for a person who oversees
more than one domain.

**Currently redundant:** it renders the same dataset/readiness/reconciliation
payload as `/operations` with a different title.

**Recommendation:** retain only as a compact summary: domain readiness, latest
source date, stale/failed count, and links to the detailed page. Do not show
duplicate charts and tables here.

### `/operations` — Operations and reconciliations

**Useful:** dataset versions, publication status, date mismatches and
reconciliation results are valuable when several workbooks are loaded.

**Currently limited:** rows have no detail link, source drill-down, or action;
the page is monitoring-only despite the word “operations”. Reconciliation rows
are also empty until participating sources share comparable dates.

**Recommendation:** keep as the detailed source-control page. Add row-level
links to the upload/DQ/source manifest and explicitly label it **Source
readiness and reconciliations** until real operational breaks/cases exist.

### `/` — Portfolio overview

**Useful:** current lots, purchase amount, derived carrying value, cash, fees,
reserves, operational total, allocation and source-backed calendar. This is the
best daily back-office landing page.

**Keep, but clarify:** the operational total and carrying value are derived and
not NAV. The current disclosures do this correctly. The “upcoming” preview is
based on dates in current lots/settlement rows, not a future settlement ledger;
the excluded `Предстоящие расчёты` section must stay visibly excluded.

**Remove or move:** the long “What the data means” glossary is useful once,
but occupies dashboard space. Move it to a collapsible **Methodology and source
policy** panel or help drawer.

### `/holdings` — Positions

**Useful:** instrument aggregation, search, asset-class filter, purchase versus
derived-carrying basis, HPR, current YTM, lot count, lot drill-down and two
Excel exports. This is the most actionable OSIP page.

**Keep, but clarify:** HPR is derived from purchase and carrying values, not an
official return. Current YTM is source-reported and should display “unavailable”
when lots disagree or the source field is absent. Add a compact tooltip explaining
that neither is an official performance metric.

**Missing:** pagination/virtual scrolling for large workbooks; the UI currently
renders the full instrument list and the lot export is the only scalable path.
The global currency selector does not change the displayed KZT valuation.

### `/cash-calendar` — Cash and calendar

**Useful:** active cash balances, zero/template toggle, currency summary,
dated lot events, source drawer and three-sheet Excel export.

**Keep, but clarify:** this is an OSIP source calendar, not a settlement ledger
or bank reconciliation. Since `Предстоящие расчёты` is deliberately excluded,
the page should say **Source dates and lot events**, not imply complete future
cash-flow coverage.

**Reduce:** the zero-template toggle is useful during source inspection but can
be secondary in the daily view. Keep it in an **Include inactive/template rows**
advanced option.

### `/data-quality` — Data quality

**Useful:** issue search/severity filters, exact source references, governed
metric catalogue, DQ export, and owner/due-date notes for findings that really
need follow-up.

**Currently too strict for local non-OSIP mode:** the red blocking banner and
acknowledgement language are correct for controlled OSIP publication, but not
for source-first domain datasets that are deliberately readable with warnings.

**Concrete bug:** the table header says **Confirmation**, but the cell renders
`source_refs.length` or “portfolio”, which is source-evidence count rather than
confirmation status.

**Recommendation:** split the view into **Source warnings** (non-blocking local
mode) and **Publication blockers** (OSIP/hosted mode). Keep assignment as an
optional note, not a required workflow. Rename the evidence column.

### `/imports` — Source uploads

**Useful:** content-based detection, multi-partition selection, explicit OSIP
portfolio assignment, immutable registry, SHA-256, version comparison,
withdrawal, and exports.

**Currently confusing:** the universal source-first wizard and the legacy OSIP
approval workflow are presented together. The generic table still offers
Approve/Publish language even though local non-OSIP datasets are auto-published.
The local operator must also understand why OSIP still requires an explicit
portfolio code.

**Recommendation:** make this a clear two-path screen:

1. **Upload domain workbook** — detect, preview, create and immediately browse;
   DQ remains visible as warnings.
2. **Upload OSIP portfolio workbook** — explicit portfolio code and optional
   controlled approval because wrong assignment changes the portfolio view.

Keep withdrawal, because it corrects an accidental source assignment without
deleting evidence. Add a direct “open dataset/source manifest” action.

### `/comparison` — Portfolio comparison

**Useful:** comparing SOBSTV and TABYS latest published snapshots by KPIs,
allocation, cash and DQ status is a valid back-office control.

**Keep, but clarify:** it always compares each portfolio’s latest published
version and uses derived-carrying allocation regardless of the global basis
selector. Show this explicitly in the page header. Report-date differences are
shown in the identity panels but should also produce a prominent mismatch note.

**Not needed yet:** comparison of non-OSIP domain datasets. That should be a
separate cross-source reconciliation view, not another comparison mode here.

### `/reporting` — Reporting

**Useful:** controlled OSIP operational CSV generation, report readiness gates,
artifact identity and repeat download.

**Currently over-positioned:** this is not a general reporting factory. It has no
domain reports, schedules, PDF/XLSX templates or submissions.

**Recommendation:** rename to **OSIP operational export** or keep it under the
Back office section. Do not present it as Portfolio Operations Insight-wide reporting until the
other domains have formal report contracts.

### `/asset-management` — Asset management

**Useful:** source-reported TABYS NAV, unit value, holdings, unit-history chart,
fund allocation and source manifest. This is the strongest non-OSIP page.

**Keep, but clarify:** “NAV” must remain **source-reported NAV**, not official
accounting NAV. SAQ is correctly detected but must not silently become the
current TABYS series. Show the selected fund/source date and whether the series
is current or stale.

**Chart decision:** keep the unit-value history and allocation chart when there
are enough observations/categories; show a table or empty state for one point or
one holding class instead of a decorative chart.

### `/treasury` — Treasury

**Useful:** own-portfolio operational total, carrying value, cash and instrument
count with basis/composition charts.

**Currently redundant:** Overview, Holdings and Cash already provide the same
OSIP facts in greater detail. The Treasury domain page also always loads the
latest SOBSTV snapshot and has no report-date/version selector.

**Concrete UI issue:** `DomainTable` has no Treasury column definition and
`domainRows` returns no Treasury rows, so the page can render a table panel with
no useful rows.

**Recommendation:** either remove the empty table and make Treasury a concise
summary linking to the OSIP detail pages, or make it the canonical OSIP page with
version selection and a meaningful cash/holdings table. Do not keep a blank table.

### `/brokerage` — Brokerage

**Useful:** trade count, turnover, buy/sell split, venue mix, execution status,
trade table and Excel export.

**Currently incomplete:** derivatives appear as a KPI and in the export, but
there is no derivatives table or detail view. Trade table has no search, date,
side, venue or execution filters. The table is capped at 250 rows.

**Recommendation:** keep the trade view and add filters/pagination. Add a compact
derivatives table or remove the derivatives KPI until the detail exists. Suppress
the venue donut when there is only one venue.

### `/clients` — Clients

**Useful:** client count, assets, client register, source references, asset
composition and client detail drawer/export. Full identifiers are appropriate
for the local supplied-workbook context.

**Currently misleading:** the “exact matches” KPI describes the optional opening-
date enrichment rather than the completeness of the client source. The main
table already shows account/IIN, while the detail subtitle says identifiers are
only shown in the detail view.

**Currently incomplete:** no client search/filter, no pagination, only the first
250 rows, and the chart shows only the top 10 clients. Negative residual
securities values correctly remain visible as a source inconsistency, but should
carry a visible DQ warning in the chart/table.

**Recommendation:** keep the page as a local domain register; rename the KPI to
**Opening-date matches (optional)**, correct the identifier copy, add search and
pagination, and label the chart **Top 10 by total assets**.

### `/corporate-finance` — Corporate finance

**Useful:** controlled deal/mandate register, issuer/subject, raw and normalized
amounts, fee/duration fields, active flag, source references and Excel export.

**Currently limited:** no status/date/issuer filters, no detail drawer, and the
 12-row chart is not useful for a single deal or a small workbook. It is not a
CRM pipeline, forecast or stage history, which is correct.

**Recommendation:** keep the register and add search/status/period filters. Make
the chart conditional on at least two comparable deals; otherwise show the
register as the primary view.

### `/accounting` — Accounting

**Useful:** source landing/DQ evidence, sheet/date/formula checks and explicit
“no official metrics” disclosure.

**Not available yet:** no financial result, budget variance, GL, balance sheet,
cash flow or accounting-approved totals should be shown until the complete
accounting package arrives.

**Recommendation:** keep as a source-readiness landing page, but avoid the
generic Finance title if it could be mistaken for a finance dashboard.

### `/risk` — Risk and limits

**Useful:** published, source-backed controls from the SOBSTV and TABYS risk
workbooks, including country, currency, open-FX, issuer, sector, instrument,
IFRS, and duration dimensions. The page now separates limit lines from the
SOBSTV exposure detail sheet and shows unresolved versus non-applicable rows.

**Not available yet:** VaR, stress, capital adequacy, risk appetite, and
scenario/sensitivity analytics are not present in the supplied workbooks and
remain unavailable.

**Recommendation:** retain the explicit source-date/DQ disclosures and extend
the governed control set only when a new workbook section supplies an auditable
threshold and actual value.

## Export audit

| Export | Decision |
|---|---|
| OSIP instrument XLSX | **Keep**; it matches the visible filtered table. Ensure quantity has integer formatting and HPR/YTM columns have explicit source/derived labels. |
| OSIP lot XLSX | **Keep**; essential for source-level investigation. |
| Cash/calendar XLSX | **Keep**; mark that upcoming-settlement rows are excluded. |
| DQ XLSX | **Keep**; export the active filters and fix the evidence/confirmation naming. |
| Import registry XLSX | **Keep**; useful for local history and correction traceability. |
| Operational CSV | **Keep for OSIP**; rename/narrow the Reporting page rather than implying a general report factory. |
| Fund/Brokerage/Client/Corporate XLSX | **Keep**; these are practical hand-off views. Include source date/version and local operational-data disclosure. |

## Recommended implementation order

### P0 — correctness and misleading UI

1. Fix or remove the non-functional global currency selector.
2. Replace the static **Read** pill with **Domain operator** in local mode and
   document the explicit OSIP exception.
3. Change local source-first wording and My Work/DQ banners from mandatory
   publication tasks to warnings/optional notes.
4. Fix the DQ table’s Confirmation/evidence column.
5. Remove the blank Treasury table and reconcile the Overview/Treasury split.
6. Add selected source/version/date context to every domain page.

### P1 — operational usability

1. Add search, filtering and pagination/virtual scrolling to clients, trades and
   corporate-finance rows.
2. Add a derivatives table or remove the derivatives-only KPI.
3. Make charts conditional on useful variation and label “top N” charts.
4. Turn Management centre into a concise landing page and Operations into the
   detailed readiness view.
5. Rename/move Reporting as an OSIP operational export page.

### P2 — later source-dependent work

- Complete accounting package and accounting metrics.
- Risk source package, limits, model metadata and validated calculations.
- Formal reporting factory, notifications, saved views and domain-aware command
  search.

## Acceptance criteria for the next revision

- Every visible filter changes the values it claims to control, or is removed.
- A local operator can identify the active domain, source file, business date and
  dataset version on every domain page.
- No local non-OSIP page requires a confirmation click merely to display source
  rows.
- No chart is rendered when it contains only one uninformative category unless
  the chart is explicitly labelled as a single observation.
- Client, trade and deal tables can reach every source row, not only the first
  250.
- Every export states its source/version, basis and operational/non-official
  status.
- Accounting and Risk remain visibly unavailable until their promised source
  packages arrive.

## Implemented in the current revision

- Removed the non-functional global currency selector and replaced it with a
  non-editable KZT context note; portfolio/snapshot/basis controls remain on
  OSIP routes where they are meaningful.
- Local mode now identifies the signed-in user as **Domain operator**, and the
  source-upload page explains that non-OSIP domain datasets are readable as
  soon as they are materialized. DQ remains visible as evidence/warnings;
  explicit OSIP approval is still available where assignment changes the
  portfolio view.
- Renamed the DQ evidence column, corrected its displayed value, and avoided
  presenting a generic “no published portfolio” state when other source
  findings are available.
- Converted Management centre into a compact summary with a link to detailed
  Operations and reconciliations, and replaced the empty Treasury table with
  links to the canonical OSIP detail pages.
- Added source/date/version context to domain pages, row search plus pagination
  for domain tables, a brokerage derivatives table, and a top-10 label for the
  client composition chart. Blank client/issuer labels now fall back to an
  account or subject instead of creating an empty chart category. The
  corporate-finance chart is suppressed when there is only one comparable deal;
  the register remains the useful view in that case.
- Added source-readiness search and status filtering, visible result counts, and
  latest business-date context on Operations so a local operator can narrow the
  registry without mistaking the summary charts for an actionable queue.
- Added `VITE_DOMAIN_SCOPE` as the local launcher pin. A domain operator can run
  a single-domain workspace by setting the variable, while `*` remains an
  explicit all-domain review scope. This keeps domain ownership clear without
  introducing hosted multi-tenant security ceremony.
- Renamed the Reporting navigation/page to **OSIP operational export** so its
  scope is explicit until formal cross-domain report contracts exist.

## Source audit implementation progress — 2026-07-21

- Corrected the Client/Brokerage adapter to ignore `Итого`, `ВСЕГО` and
  `ВСЕГО по счету` subtotal rows.  The real workbook now reconciles to 197
  clients, 202 positions, KZT 9,929,901,565.224399 cash and KZT
  98,837,071,968.864961 total assets; aggregate rows remain source evidence
  rather than becoming duplicate clients.
- Added the `client_maturity_calendar` child dataset from the workbook's
  `календарь погашения` sheet.  It is independently versioned, published in
  the Clients/Brokerage read models and included in the Russian XLSX export.
  Its dates, coupon fields and event values are source values; no `TODAY()`
  calculation is introduced.
- Corrected the derivatives view/export to use the actual `Лист7` contract:
  instrument type, identifier, market, underlying/rating, counterparty,
  quantity, amount, currency, settlement date and obligation status.
- Corrected Corporate Finance ISIN extraction for text such as
  `ISINXS3363342927`; the normalized list now contains `XS3363342927` while
  preserving the original subject text.  Corporate Finance charts now keep
  USD and KZT amounts in separate series instead of adding currencies.
- Updated domain tables with source-backed maturity/coupon fields and the
  additional Corporate Finance mandate fields.  The remaining planned work
  is TABYS reconciliation/price coverage and richer client/trade/deal filters.
- Added the cached `Клиенты` sheet as a separate `client_dashboard_snapshot`
  dataset for manager/type/opening-date and client concentration views.  Its
  totals are reconciled against the canonical `Лист4` account register; the
  current workbook differs by a medium-severity DQ finding, so KPI cards use
  `Лист4` while manager distribution uses the explicitly labelled `Клиенты`
  source.
