# Reusable Excel-export design standards

Status: adopted for the holdings export; apply to every new or materially changed
workbook export.

This document records the design choices that made the holdings workbook
understandable, auditable, and safe to extend to other domains. It is a
convention, not a requirement to copy the holdings sheet layout literally.

## 1. Source-first semantics

- Preserve the value supplied by the source workbook and keep its source
  workbook, sheet, row, and (where available) cell reference.
- Give every calculated value a distinct label. A calculated operational value
  must not be presented as official NAV, market value, settlement, or a paid
  cash-flow ledger unless the source actually supports that claim.
- Keep source, derived, and unavailable states visible in the workbook. Do not
  replace a missing input with zero or a plausible-looking estimate.
- Treat classification dictionaries as presentation/enrichment layers. They
  may improve grouping, but must not overwrite raw source evidence.

## 2. Units, currencies, and quote scales

- Put the unit and currency in the header whenever a value could be ambiguous:
  `KZT`, `USD`, `валюта цены`, `нативная валюта`, and `%` are part of the
  contract, not decoration.
- Keep native values and presentation equivalents in separate columns. Never
  silently convert a source amount or infer a quote basis from the instrument
  type.
- Preserve numeric cells as numeric cells, with an explicit number format.
  Identifiers, labels, and `Недоступно` remain text; they are not coerced into
  numeric zeroes.
- A nominal is a face-value/reference field, not a unit price. Purchase price,
  carrying price, nominal, quantity, purchase amount, and carrying amount must
  remain separate fields until the source explicitly defines how they relate.
- Do not introduce a universal “per 100 nominal” conversion unless the source
  documents that convention for the relevant instrument and column.

## 3. Formulas and income treatment

- Put the formula in the audit documentation and in a visible workbook note.
  State the inputs, currency, timing rule, and missing-input behavior.
- For holdings HPR, the current carrying value includes the current accrued
  coupon once. Historical income is added only when supported by source data:
  received Bloomberg dividends, or the clearly labelled estimated paid-coupon
  amount for coupon-bearing lots.
- The coupon estimate is an approximation, not proof of payment:
  `nominal × quantity × coupon rate × holding days / 360`, less the accrued
  coupon already included in carrying value, floored at zero. This prevents
  double-counting while avoiding a claim that a coupon ledger exists.
- Dividend entitlement is evaluated per lot using its purchase date and the
  report/as-of date. The Bloomberg dictionary applies the existing US-listed
  15% withholding rule; its freshness is disclosed. Future expected dividends
  and coupons belong in the cash-flow view and are excluded from historical
  HPR.
- Name percentage columns explicitly by currency, for example
  `HPR (расч.), KZT, %` and `HPR (расч.), FX, %`. The FX percentage is the
  USD-equivalent return where conversion is supported. Do not use an unlabeled
  `HPR, %` when currency conversion can affect interpretation.
- If a required input is absent, return `Недоступно` (or `Неприменимо` when the
  metric does not apply) rather than mixing a partial calculation with a
  complete-looking total.

## 4. Provenance and control evidence

- Every displayed metric should be traceable to a source row/cell or to a
  documented formula over traceable inputs.
- Keep a control/provenance sheet or section containing, as applicable:
  report date, portfolio/scope, source version, selected filters, row counts,
  source dates, freshness warnings, value-basis selection, and reconciliation
  results.
- Show the population used for totals. For filtered exports, totals and
  control counts must be calculated from the same filtered rows displayed in
  the table.
- Use explicit status text for data quality: source missing, stale, estimated,
  not applicable, and unavailable are different states.
- Keep the original source file immutable and retain the export/audit event;
  presentation changes must not rewrite source evidence.

## 5. Workbook layout and navigation

- Give each continuous table a title/metadata area, one unambiguous header row,
  autofilters, readable widths, wrapped long text, and typed dates/numbers.
- Freeze everything through the first header row and freeze column A. The
  implementation is `B<header_row + 1>`; do not hard-code “freeze six rows”
  because metadata length varies between exports.
- Module summary/dashboard sheets (stacked tables feeding charts, e.g.
  `Сводка ФО`, `Сводка по лимитам`) do not freeze panes at all - they're read
  chart-first, not scrolled as a long table, so a frozen column A has nothing
  to do there. `Данные графиков` (the chart-helper-data sheet, see below)
  follows the same rule. Any other stacked/helper sheet with unrelated
  sections still freezes column A only (`B1`) and documents the exception. Do
  not pin one section's header over a different section.
- Leave enough vertical space between metadata, tables, and charts. Charts
  must not cover source tables or control totals.
- Keep chart helper data on a dedicated `Данные графиков` sheet (or a clearly
  labelled helper section) and reference typed cells. A chart is a view of the
  table, not a second undocumented source of truth.
- Avoid overlapping merged cells. Use merges only for presentation titles and
  verify the resulting XLSX opens without repair in Excel.

## 6. Notes and language

- Use the workbook's primary language consistently. If the export is Russian,
  translate explanatory notes and labels; retain English field names only when
  they are source identifiers or API names, and explain them where useful.
- Put a short note near the table explaining basis and limitations. For
  example: operational carrying value is not official NAV/market value; source
  quote scale is unknown; USD equivalents use the disclosed dated FX rate; and
  estimates are not payment evidence.
- Make badges, headers, tooltips, and API/UI labels say the same thing. A field
  called `Текущая цена` is unsafe when it is actually a carrying-price or
  accounting-value calculation.

## 7. Validation checklist for every export

Most of the list below is enforced automatically by `tests/export_compliance.py`'s
`assert_workbook_is_compliant`, run against every export endpoint in
`tests/test_export_compliance.py` plus the existing module-export tests in
`tests/test_multi_source.py`, against real OSIP (SOBSTV) and TABYS
fixtures where the export is portfolio-scoped. It checks: archive
integrity (item 1), freeze panes and header-row detection (item 2, via
`sheet.auto_filter.ref`), that no numeric/date value was accidentally
written as text and no numeric/date-formatted column mixes typed and
text-shaped values (item 3), no bare empty-string cells standing in for
`Недоступно`/`Неприменимо` (missing-value semantics, item 3), overlapping
merged ranges (item 4), literal Excel error values (item 3), and that no
chart is anchored on top of the sheet's primary filterable table (item 5).
Call it against any new or changed generator's output rather than
re-deriving these checks by hand. The exceptions it's aware of (stacked
multi-table sheets, the deliberate `Сделки` first-header-freeze case, the
trivial `Нет данных` placeholder) are recorded in the matrix in
`docs/export-column-audit.md`'s "Workbook navigation standard" section.

Two items are **not** automatable and remain manual: a literal `###`
column-too-narrow display artifact (Excel decides this from actual
rendered pixel width/font metrics, neither of which round-trips through
a saved `.xlsx`) and true rendered chart/table pixel overlap (the checker
only catches a chart anchored *inside* the table's own cell range, not a
visually-overlapping chart anchored just outside it).

Before releasing a changed generator, check both the workbook structure and a
representative workbook from each supported source family (for example OSIP and
TABYS):

1. Load with `openpyxl` and test `unzip -t` on the XLSX archive.
2. Confirm expected sheet names, header rows, freeze panes, filters, and chart
   anchors.
3. Confirm numeric/date cells are typed correctly and no visible value is
   rendered as `###`, `#REF!`, `#DIV/0!`, or `#VALUE!`.
4. Check merged ranges for overlap and verify Excel does not report repaired or
   removed records.
5. Reconcile totals, weights (normally 100% where applicable), row counts, and
   HPR amounts/percentages back to the displayed population.
6. Verify native-currency values are not silently rescaled and that equivalent
   currency columns are unavailable when their FX inputs are unavailable.
7. Verify source links/provenance survive filtering and aggregation.
8. Verify missing, stale, estimated, and not-applicable cases with fixtures;
   do not validate only the happy path.
9. Run the backend/frontend export tests and a production build. If a local
   renderer is available, visually open the workbook in Excel/LibreOffice as a
   second check; structural validation remains mandatory.

## 8. Export implementation template

Each export module should have a short companion audit entry containing:

| Item | Required decision |
|---|---|
| Workbook purpose | Operational, source evidence, or both |
| Sheets | Name, population, and whether the sheet is continuous or stacked |
| Header/navigation | Header row rule, freeze pane, filters, and first-column behavior |
| Source mapping | Source workbook/sheet/row/cell for each important field |
| Formulas | Formula, units, timing, rounding, and missing-input behavior |
| Currency/scale | Native basis, conversion source/date, and unavailable behavior |
| Provenance | Detail links, control totals, freshness/version disclosure |
| Validation | Fixtures, structural checks, visual check, and test command/result |

When a new export intentionally deviates from this standard, record the reason
next to the exception and add a regression test for it.
