# Portfolio Operations Insight — data provenance audit (21 July 2026)

## Scope

This audit checks that numerical values rendered by the current pages, KPI cards, tables and charts resolve to the imported `sources/` workbooks, or are explicitly labelled as derived/unavailable. It covers the persistent demo service database after loading all supported workbook inputs. It does not treat interface copy, translations, icons, workflow labels or disclosures as source data.

The source directory currently contains eight supported workbooks:

| Workbook | Detected feed | Published/visible use |
|---|---|---|
| `Бэк офис_УИП_ ОСИП ТАбыс 19.07.2026.xls` | OSIP portfolio | TABYS snapshot |
| `Бэк офис_УИП_ ОСИП собственный портфель 19.07.2026.xls` | OSIP portfolio | SOBSTV snapshot |
| `Бэк офис_УИП_ Портфель TABYS Capital -19.07.26.xlsx` | TABYS valuation | valuation, holdings, cash/liabilities, NAV history, prices |
| `Бэк офис_УИП_ Стоимость пая Tabys Capital 19.07.2026.xlsx` | unit history | TABYS unit series; SAQ retained as validated/non-current |
| `Клиентский_дашборд.xlsx` | client/brokerage | clients, trades, derivatives, opening dates |
| `Направление_Корпфин_01072026.xlsx` | corporate finance | deal register |
| `Бухгалтерия_Бюджет 2026.xlsx` | accounting landing | validated evidence only |
| `Бухгалтерия_Портфель.xls` | accounting landing | landing evidence; no Finance metrics |

Lock files (`~$...`), `desktop.ini` and the DOCX note are intentionally not workbook inputs.

## Provenance contract

* Every persisted `dataset_record` has `raw_values`, `formulas`, `cached_values` and a non-empty `source_ref` containing workbook, sheet and row information.
* OSIP lot, cash, settlement, calendar and DQ responses expose the same source reference on every row. Aggregated instrument and allocation values are computed only from those persisted lots; they do not replace the lots.
* Multi-source domain records include a `source` object containing the original filename plus sheet/row reference. The domain tables now show that evidence in a visible `Source/Источник` column.
* Source manifests on domain pages identify dataset version, source filename, source date, business date and publication status. Date mismatches are displayed rather than silently merged.
* Financial decimals remain strings in the API. Formatting, sorting, grouping and chart aggregation happen in the read model/UI and do not alter the stored source values.
* “Source” means source-reported or directly parsed input; “derived” means a documented aggregation/formula; “unavailable” means no supporting source exists. Official NAV, official performance, risk metrics and accounting metrics remain unavailable.

## Page/widget/graph traceability

| Page | Rendered values | Source path and basis | Result |
|---|---|---|---|
| Portfolio overview | lot/instrument counts, purchase, carrying value, cash, fees, reserves, operational total | Published `portfolio_snapshot`; counts/fees/reserves are source fields; carrying and operational total are recalculated from OSIP lots/cash. Allocation is grouped from the same lots. Calendar rows retain settlement/lot source refs. | Pass; source/derived badges are accurate. Official NAV is unavailable. |
| Positions | instrument table, HPR, current YTM, quantity, values, weights; lot drawer | Published OSIP `position_lots` and `source_rows`; HPR and weights are deterministic read-model calculations. HPR also incorporates eligible rows from `sources/dividends.xlsx` using each lot's purchase date and the current date; US-token tickers use the 15% withholding rule. Current YTM is shown only when all lots in an ISIN agree; otherwise unavailable. | Pass; every lot has a workbook/sheet/row reference, and dividend eligibility is covered by unit tests. |
| Cash and calendar | cash rows, KZT equivalents, currency summary, event counts and event table | Published OSIP cash balances, settlement events and lot dates; upcoming settlement rows are intentionally excluded at import time. Currency totals are aggregation only. | Pass; every cash/event row carries source refs. |
| Data quality | DQ counts, severity filters, issue rows, acknowledgement/remediation state | Published OSIP DQ records plus independently published dataset issues from the source registry. Issue evidence points to workbook/sheet/rows. | Pass; DQ counts are source records, not synthetic error counts. |
| Uploads | OSIP registry, source detection, child dataset workflow, comparison and audit | Immutable `source_uploads`, `import_batches`, dataset versions and audit events. | Pass; demo fixture rows are hidden when a real source exists for the same dataset/scope. |
| Comparison | two latest published OSIP snapshots, KPI deltas, allocation and cash comparison, DQ severity counts | Two published snapshot APIs; deltas and percentages are derived from the two source-backed responses. | Pass; missing side values are unavailable or zero only when an asset class is absent. |
| Reporting | workflow gates, DQ gate counts and controlled CSV generation | Published snapshot/readiness API and audit-backed report artifacts. | Pass; official report remains unavailable. |
| Asset management | source NAV, unit value, securities, holding count; unit-value area chart; holdings donut | TABYS `fund_valuation`, `fund_unit_series`, and `fund_holdings` records from the two TABYS workbooks. Chart values are source observations or grouped purchase values. | Pass; SAQ is not used as current TABYS data. |
| Treasury | operational total, carrying value, cash, instrument count; basis comparison and composition charts | Published SOBSTV OSIP snapshot. Purchase/carrying/cash values are source-backed or documented derived totals. | Pass; source/business date mismatch is surfaced. |
| Brokerage | trades, KZT turnover, client assets, derivatives; buy/sell and venue charts; trade table | `Клиентский_дашборд.xlsx` child datasets. Turnover and venue charts use parser summaries from source trade rows. | Pass after real-source precedence fix; date mismatch is surfaced. |
| Clients | client count, assets, exact matches, client table and asset-composition chart | Client snapshot and opening-date children from `Клиентский_дашборд.xlsx`; asset composition is `total_assets - cash` and labelled derived. NNA is unavailable. | Pass; negative residuals are no longer clamped to zero. |
| Corporate finance | deal count, active count, period, deal table and placement/demand chart | `Направление_Корпфин_01072026.xlsx`; normalized amounts retain original raw text. Ambiguous units are excluded from the chart and remain DQ evidence. | Pass; forecast/pipeline is unavailable. |
| Operations/management | dataset-status and scope charts, dataset table, reconciliation table | Published/validated dataset-version registry and reconciliation results. | Pass; demo children are excluded from default readiness once real children are loaded. |
| Accounting | source-readiness/landing evidence only | The two accounting workbooks are stored and inspected, but no accounting KPI is rendered. | Intentional placeholder. |
| Risk and limits | source-pending state only | No risk workbook has been supplied; no risk number is invented. | Intentional placeholder. |

## Checks executed

* Persistent database integrity: SQLite `PRAGMA integrity_check = ok`; no foreign-key violations.
* Dataset integrity: no failed imported children, duplicate record keys or duplicate published dataset keys.
* Source references: all 13,414 persisted records from non-demo multi-source datasets have non-empty source references; all published OSIP holdings, cash, calendar and DQ rows have source references.
* Live API manifests after the source load: Asset Management 6 datasets, Brokerage 3, Clients 2, Corporate Finance 1; all record rows returned by these modules have a filename, sheet and row reference.
* Live OSIP snapshots: SOBSTV and TABYS latest published snapshots expose source references for holdings, cash, calendar and DQ rows.
* Backend tests: `62 passed, 1 skipped` before the provenance-specific regression test; after the test and importer changes, the targeted multi-source suite is `6 passed`.
* Frontend tests: `23 passed`; production Vite build succeeds.

## Findings and fixes made during this audit

### Demo data could override real source data

The local demo database contains sanitized `demo_*.xlsx` fixtures. Before this audit, `latest_published()` selected the synthetic brokerage trade/open-date datasets when their synthetic business date was newer than the real workbook. This meant the Brokerage and Clients pages could display demo values after a real upload.

The read model now sorts imported source uploads ahead of demo fixtures and hides demo siblings from default dataset readiness/registry reads once a real dataset exists for the same type and scope. Demo data remains immutable audit evidence and is still available on a fresh installation before real sources are loaded. A regression test covers this precedence rule.

### Client chart silently changed source-derived values

The client composition chart used `Math.max(total_assets - cash, 0)`, which hid an inconsistency by replacing a negative residual with zero. It now uses the exact difference. Any negative result remains visible and must be handled through DQ, rather than being silently repaired in the UI.

## Remaining limitations (not provenance failures)

* Chart tooltips remain intentionally value-focused. The interactive source badge in
  each KPI/chart header opens the workbook, sheet, row, column and cell evidence;
  aggregate cards also disclose when no single source cell can represent the
  total.
* Accounting and Risk are deliberately source-pending. No values are calculated for them.
* Official NAV, official performance, external market prices, formal client flows/NNA and accounting-approved totals are not supported by the supplied workbooks and remain unavailable.
* Source date differences are real characteristics of the supplied files. The application displays them and does not shift or silently reconcile dates.
