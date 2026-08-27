# Role-based workflow and UI plan — Portfolio Operations Insight

**Date:** 21 July 2026  
**Scope:** the five independent operating owners currently expected to use the application: Бухгалтерия (Accounting), Бэк офис (Back office), Клиентский (Client operations/Brokerage), Корпфин (Corporate finance), and Risk manager.

This is a product/workflow plan, not a claim that all five domains are complete. The supplied source folder currently contains files for the first four areas and no risk-manager package. One additional accounting file is also expected but has not been supplied. Accounting therefore remains a controlled landing/DQ area, and Risk remains a source-readiness placeholder.

> **Operating-model update:** the application is currently run locally by the
> owner of one domain using that domain's own workbooks. The canonical security
> and workflow interpretation is now [`local-domain-operating-model.md`](local-domain-operating-model.md).
> The stricter four-eyes, per-client matching, masking, and publisher-gate
> recommendations below describe a possible future hosted deployment; they are
> not prerequisites for the local read-only dashboard.

## 1. Operating model

Each operator should see a focused work queue for their domain rather than a global upload screen. A workbook is an immutable physical source. In the intended source-first mode, the operator uploads their own workbook, reviews the visible DQ/mapping/provenance warnings, and can immediately use the parsed domain pages, charts, and exports. A separate reviewer is optional and is not required for normal operation. Multiple operators may share a domain, but each sees only source packages whose uploader identity matches their own actor identity unless an explicit governance/admin role grants cross-uploader access.

The common lane is:

`received → detected → mapped → validating → validated → available to the domain owner`

with `failed`, `rejected`, `superseded`, and `withdrawn` retained as evidence.
A correction creates a new version; it does not overwrite the previous version.
Every available view must show the source filename, dataset type, source report
date, business date, generated-at timestamp, parser version, availability state,
and DQ/reconciliation status. A later shared or regulated deployment may insert
independent approval/publication steps without changing the source lineage.

### Recommended access model for a future hosted deployment

If the application later becomes shared or begins writing to downstream systems,
use the existing four-eyes workflow (`uploader`, `reviewer`, `publisher`,
`reader`) with domain scopes:

| Domain scope | Owner | Minimum useful permissions |
|---|---|---|
| `accounting` | Бухгалтерия | upload, map, review, publish accounting landing datasets |
| `back_office` | Бэк офис | upload, map, review, publish OSIP and fund datasets |
| `client_ops` and `brokerage` | Клиентский | upload and operate client/trade/derivatives datasets; local source identifiers are visible to the owner |
| `corpfin` | Корпфин | upload, map, review, publish corporate-finance register |
| `risk` | Risk manager | upload, map, review, publish risk datasets when delivered |

Those controls are not required for the current local owner workflow. Today the
domain is the primary workspace; the same local operator may upload, inspect,
export, and publish source-first domain data. A user may still select another
domain locally for testing, but this is not intended as enterprise access
control.

## 2. Source inventory and current readiness

| Owner | Current files | Current usable partitions | Current limitation |
|---|---|---|---|
| Бэк офис | `Бэк офис_УИП_ ОСИП ТАбыс 19.07.2026.xls`; `Бэк офис_УИП_ ОСИП собственный портфель 19.07.2026.xls`; `Бэк офис_УИП_ Портфель TABYS Capital -19.07.26.xlsx`; `Бэк офис_УИП_ Стоимость пая Tabys Capital 19.07.2026.xlsx` | OSIP snapshots; fund valuation, holdings, cash/liabilities, NAV history, prices; TABYS and SAQ unit series | Missing/stale prices, broken/external formulas, ordering/duplicate/missing unit values; SAQ is stale and inactive |
| Клиентский | `Клиентский_дашборд.xlsx` | client/account snapshot, trades, derivatives, opening-date reference | `Лист8` trade mapping currently produces unknown currencies/instruments; 245 opening dates unmatched and 1 ambiguous; cached “свободные остатки” is evidence only |
| Корпфин | `Направление_Корпфин_01072026.xlsx` | corporate-finance register and period summary | ambiguous amount/unit in one or more rows; commission rate missing in one row; no pipeline history/forecast |
| Бухгалтерия | `Бухгалтерия_Бюджет 2026.xlsx`; `Бухгалтерия_Портфель.xls`; one expected accounting workbook missing | landing sheets, formula/date/schema DQ evidence only | budget filename says 2026 while title says 2021; portfolio workbook has conflicting dates and `#REF!`/external formulas; official accounting metrics must not be published |
| Risk manager | no files supplied | none | no CAR, limits, exposures, curves, volatility/correlation, scenarios, model version, or capital/liquidity inputs; no risk metrics may be invented |

The detailed page/widget lineage is in [`data-provenance-audit-2026-07-21.md`](data-provenance-audit-2026-07-21.md). The cross-domain feature gaps are in [`product-feature-gap-register.md`](product-feature-gap-register.md).

The operational role-to-workbook and reference-dictionary matrix is maintained
in [`domain-upload-instructions.md`](domain-upload-instructions.md).

## 3. Shared UI pattern

Every domain opens on a compact “My work” page:

1. **Needs my action** — cards linking to files awaiting mapping, DQ remediation, review, approval, or publication.
2. **Latest published** — one row per dataset/scope with source date, business date, version, status, and freshness.
3. **Data warnings** — blockers, date mismatches, stale sources, and unresolved mappings; clicking a card opens the exact evidence row.
4. **Recent activity** — the owner’s uploads, reviews, exports, and withdrawals.

The upload wizard should be domain-aware:

`Select file → Detect feed → Choose partitions/scope → Mapping preview → DQ and reconciliation → Submit for review`

For a hosted/controlled deployment, the mapping preview is mandatory for
non-OSIP files. It shows source sheet/row/column beside the normalized field
and sample values; no broad “Publish all” action is allowed. In the local
source-first deployment the same preview is useful evidence, but confirmation
is optional and successfully parsed children are immediately readable. Each
child dataset still has its own status badge and action menu.

Use the same visual vocabulary throughout:

- `Источник / Source` — copied from the workbook;
- `Расчётный / Derived` — deterministic application calculation;
- `Недоступно / Unavailable` — required source data is absent;
- `Проверка / DQ` — a control finding, never silently corrected;
- `Дата источника`, `Рабочая дата`, and `Сформировано` shown separately;
- “Операционные / расчётные данные; не официальный NAV” wherever a metric is not an official accounting/NAV result.

## 4. Бэк офис workflow

### Sources and responsibilities

The back-office user owns OSIP portfolio snapshots and the TABYS valuation/unit-history feeds. “Предстоящие расчёты” remain excluded. The user chooses the explicit OSIP portfolio assignment; filename text is retained as evidence but never used as the identity rule.

### Daily workflow

1. **Receive and detect.** Upload one workbook. The detector identifies OSIP, TABYS valuation, or unit history from stable sheet/header structure.
2. **Assign scope.** For OSIP, select `SOBSTV` or `TABYS`; confirm report date and internal source date. For valuation/unit history, confirm `TABYS` or `SAQ` and the child partitions.
3. **Preview.** Show lots, instruments, cash, liabilities, NAV, unit counts, prices, and source references before creating a child version.
4. **Reconcile.** Show OSIP carrying value vs valuation securities, OSIP cash vs valuation cash, securities + cash − liabilities vs reported NAV, and NAV ÷ units vs source unit value. Each has tolerance, actuals, difference, and date comparison.
5. **Inspect DQ.** Open missing/stale prices, broken formula evidence, duplicate/out-of-order unit dates, and missing values. In local source-first mode these are warnings that may be annotated but do not require acknowledgement; in a controlled/hosted workflow, acknowledgement requires a justification. Never change source evidence.
6. **Review and publish.** In local source-first mode, a successfully parsed child is readable immediately. DQ and reconciliation findings remain visible and must not be described as clean or official. Independent review/publication remains the hosted-deployment option.
7. **Operate.** Use Overview, Positions, Cash/Calendar, Comparison, DQ, and Russian Excel exports. Compare corrections by dataset/scope/business date.

### Recommended UI

- **Back-office home:** “Новые загрузки”, “Ожидают проверки”, “Блокеры DQ”, “Несовпадение дат”, and “Последняя опубликованная версия”.
- **Portfolio selector:** `SOBSTV · 20.07.2026` and `TABYS · 20.07.2026`, with version and publication state visible in the option.
- **Fund feed panel:** separate cards for `Оценка`, `Позиции`, `Деньги/обязательства`, `История NAV`, `Цены`, `Паи TABYS`, and `Паи SAQ`. Each card has its own status and source date.
- **DQ drawer:** rule, severity, exact sheet/row/cell, source value, optional local note, and (in controlled mode) acknowledgement code, owner, due date, and reviewer decision.
- **Publish checklist (controlled/hosted mode):** independent approval, all current blocker/high acknowledgements, reconciliations, date freshness, and a final source-manifest download. Local source-first mode shows the same evidence without requiring the checklist to make parsed data readable.

### Back-office controls

Never hide a date mismatch or turn missing prices into zero. Keep SAQ labelled stale/inactive until explicitly approved. Current TABYS high findings (`TABYS-PRICE-01`, `TABYS-EVIDENCE-02`, `UNIT-02`, `UNIT-04`, `UNIT-06`) should be visible in the queue before publication.

## 5. Клиентский / Brokerage workflow

### Source partitions

Use `Лист4` for the client/account/position snapshot, `Лист8` for trades, `Лист7` for derivatives, and `Лист6` for opening dates. Presentation sheets are reconciliation evidence. `свободные остатки` contains cached formula results and must not be treated as a canonical ledger.

### Daily workflow

1. Upload and detect the client workbook; show its as-of date (20 July 2026 in the supplied file).
2. Review the sheet-to-field mapping. For `Лист8`, confirm trade date, venue, client, account, side, quantity, price, currency, instrument, and execution status with real sample rows.
3. Publish client/account snapshot, trade ledger, derivatives, and opening-date reference independently.
4. Treat the workbook's client/account rows as the canonical client view. Opening-date matching is optional enrichment; the 245 unmatched names and one ambiguous name remain visible as non-blocking source findings and do not require manual decisions.
5. Operate client search, brokerage trading, derivatives/maturity calendar, reconciliation queue, and audited exports.

### Recommended UI

- **Client operations home:** assets, securities, cash, client/account count, source freshness, unmatched opening dates, trade-mapping health, and upcoming derivative events.
- **Client register:** filters for manager, branch, account type, residency, segment, status, and source date. In the local domain workspace, show the identifiers supplied by the workbook directly; a future hosted deployment may add masking and an authorized detail drawer.
- **Client detail drawer:** source-linked identity, accounts, holdings, cash, total assets, opening-date match state, source dates, and audit history.
- **Brokerage page:** trade table with business date, buy/sell, venue, instrument, quantity, price, gross/net amounts, currency, and execution status. Show a prominent “Mapping confirmed” badge before enabling turnover and buy/sell charts.
- **Identity enrichment:** source names, candidate accounts, and source rows are informational. Manual resolution remains available only when a downstream join is later needed.
- **Exports:** visible “Экспорт” actions. Keep PII out of URLs, telemetry, and exception text; the local workbook export may contain the same identifiers as the supplied source.

### Critical current issue

The supplied `Лист8` child has 8,732 trades, but its current summary reports `Не указано` for turnover currency and instrument mix, while execution-status counts contain numeric values. This indicates a column-mapping defect or an unverified header offset. It is a P0 fix: the UI must show a mapping preview and block brokerage KPI publication until the canonical fields are verified against the workbook headers.

## 6. Корпфин workflow

### Daily workflow

1. Upload `Направление_Корпфин_01072026.xlsx`; detect the `Дашборд` register.
2. Preview raw cell text beside normalized issuer, mandate subject, ISIN set, placement amount/currency, satisfied demand, investors, commission rate, received fee, duration, and active flag.
3. Resolve ambiguous amount units/currencies and missing commission rate. Store the raw text and the resolution, never overwrite it.
4. Approve and publish the register independently from any future CRM or accounting feed.
5. Filter by period, issuer, active status, unresolved DQ, and source date. Export the register with source references.

### Recommended UI

- **Corporate-finance home:** period selector, deal count, active mandates, unresolved unit count, missing commission count, and latest source freshness.
- **Deal register:** issuer, mandate/subject, ISINs, raw and normalized amounts, satisfied demand, investor count, commission, fee, duration, active status, DQ, and source cell.
- **Deal detail drawer:** deterministic surrogate key, original text, normalized fields, source row/cell, version history, reviewer decisions, and audit trail.
- **Summary chart:** placement versus satisfied demand only for unambiguous rows. Clearly label the chart as source/derived; do not display forecast pipeline, conversion rates, or future stages without another source.

### Controls

The current register has `CORPFIN-01` (ambiguous amount/unit) and `CORPFIN-03` (missing commission rate). These remain visible as unresolved DQ and should not be presented as zero.

## 7. Бухгалтерия workflow

### Current scope

The two available files are a landing/DQ package, not an authoritative accounting feed:

- `Бухгалтерия_Бюджет 2026.xlsx` is titled “БЮДЖЕТ НА 2021 ГОД” despite the filename and has budget/actual period columns.
- `Бухгалтерия_Портфель.xls` contains conflicting period/title evidence and `#REF!`/external-link formulas; one visible sheet refers to a 2013 date.
- One additional accounting file expected from the team is missing.

### Recommended workflow now

1. Upload each workbook independently.
2. Inspect every sheet, formula and cached value; classify P&L, balance, cash, budget, actual, and supporting schedules.
3. Review date/title conflicts, broken references, unsupported formulas, units and currencies.
4. Download raw evidence and assign DQ owners. Keep children in `validated`/`rejected`/`landing` status as appropriate; do not publish Finance KPIs.
5. When the missing authoritative file arrives, map it through the same wizard and define the accounting metric contract before enabling a Finance page.

### Recommended UI

- **Accounting source readiness:** expected files, received files, periods, formula-error count, date conflicts, schema coverage, and a red “Landing/DQ only — official accounting totals unavailable” banner.
- **Workbook inspector:** sheet list, dimensions, title/date evidence, formula-versus-cached view, broken-reference list, and source-cell links.
- **DQ queue:** date conflict, `#REF!`, external link, unsupported formula, missing required section, unit/currency ambiguity, and reviewer decision.
- **Future Finance page (not enabled now):** P&L, balance, cash, budget-versus-actual and reconciliation only after the source package and accounting approval are complete.

## 8. Risk manager workflow

No risk source files have been supplied. The correct experience is an onboarding contract, not demo numbers.

### Source-readiness page

Display a checklist for:

- positions and exposures with instrument/account identifiers;
- instrument master and risk classifications;
- yield curves, prices, volatility and correlation inputs;
- capital, liquidity and official regulatory inputs;
- risk limits, owners, exceptions, review dates and policy versions;
- scenario definitions, shocks, model/version and as-of date;
- approval, publication and audit requirements.

Each requirement has `Ожидается`, `Получен`, `Проверка`, or `Опубликован`, with an upload action and a sample schema. No CAR, buffer, FX exposure, VaR, stress or appetite chart is shown until the required source and model version are approved.

### Future risk workspace

1. Risk overview with source basis/date on every metric.
2. Risk-appetite and limits matrix with exposure, limit, utilization, status, owner and next review.
3. Scenario lab (for example USD +10%, rates +200bp, equities −15%) with explicit model/version and derived label.
4. Breach/remediation queue with independent review and publication.

## 9. Cross-domain navigation and ergonomics

The left navigation should be filtered by domain scope, with a global “Source uploads” and “Data quality” entry available to authorized reviewers. A person should land on their own queue, not on a management page full of unrelated actions.

Recommended top-level structure:

- **My work**
- **My sources / Upload**
- **My datasets**
- **My DQ and reconciliations**
- Domain pages (only for assigned scopes)
- **Exports and audit**

Use a consistent right-side detail drawer so a user never loses their table context. Put the action button next to the unresolved item (“Map columns”, “Resolve DQ”, “Request review”, “Publish”, “Withdraw”), not in a remote toolbar. Show a progress lane and a clear next owner after every action.

Use domain-specific default filters and dates. Preserve raw workbook language and cell references. Translate application labels through the RU/EN catalogue, but never translate evidence text in a way that changes its meaning.

## 10. Delivery backlog

### P0 — before relying on operational output

1. Add domain-scoped permissions and “My work” landing pages.
2. Add the universal mapping preview; confirmation is optional in local source-first mode.
3. Fix and golden-test `Лист8` trade-column mapping; show unreliable fields as DQ/unavailable rather than blocking the source view.
4. Keep the client opening-date exception list informational; add manual resolution only if a later downstream join needs it.
5. Make source date, business date, generated-at and freshness visible on every dataset.
6. Keep Accounting as landing/DQ only and Risk as source pending.
7. Keep independent child lineage and replacement history; local source-first mode may publish parsed children automatically, while hosted mode can retain independent approval.

### P1 — operational comfort

1. Implement the role-specific home queues and task counts.
2. Add source-linked detail drawers and per-domain exports.
3. Add version comparison and “what changed” summaries per child dataset.
4. Add notifications for blockers, stale sources, failed imports and pending review.
5. Revisit masking/reveal controls only if the app becomes hosted or multi-user; local domain owners can see source identifiers directly.

### P2 — after missing source packages arrive

1. Integrate the additional accounting workbook and define official accounting metrics.
2. Integrate the risk package, model governance and approved stress/limit calculations.
3. Add cross-domain reconciliations (accounting ↔ portfolio ↔ client/brokerage) only after ownership and date contracts are agreed.

## 11. Acceptance criteria by owner

| Owner | Must be able to do | Must be impossible to do silently |
|---|---|---|
| Бэк офис | upload, assign OSIP portfolio, review fund partitions, reconcile, publish/withdraw, export | include “Предстоящие расчёты”, hide stale/missing prices, imply official NAV |
| Клиентский | inspect source clients, view optional identity enrichment, publish/export | fuzzy-join clients, expose PII in URLs/logs, publish turnover from unmapped columns |
| Корпфин | resolve units, review raw/normalized deal fields, publish register, export | guess ambiguous amounts, turn missing commission into zero, show unsupported pipeline forecasts |
| Бухгалтерия | inspect sheets/formulas, manage DQ evidence, upload missing package, publish only approved accounting children | publish official P&L/NAV from landing files or broken formulas |
| Risk manager | see source contract, upload future packages, validate model/input partitions, publish approved risk children | display CAR/VaR/stress/limits using invented or demo values |

## Conclusion

The safest and most intuitive design is five domain work queues over one shared immutable-upload and child-dataset workflow. Back office can operate the portfolio/fund feeds now; Client operations can operate client snapshots and derivatives after the trade mapping is corrected; Corporate finance can operate a controlled register after unit resolution; Accounting should remain evidence/DQ only until its missing authoritative file arrives; and Risk should remain a transparent source-readiness page until its inputs exist.

## Implementation status — first P0 slice

The first implementation slice is now in place:

- The Client/Brokerage `Лист8` parser resolves fields from header text instead of assuming that blank spacer columns are business fields. This corrects quantity, amount, currency, ISIN, security type, prices, yield, settlement date, and execution status.
- Each trade dataset now exposes a mapping summary (`header_row`, matched/missing fields, confidence, and `mapping_confirmed`). Missing required mappings create high-severity `BROKERAGE-MAP-01` DQ evidence.
- Low-confidence trade mappings remain explicit DQ evidence; local source-first mode does not require a reviewer click before showing the source-backed rows. Hosted mode may require confirmation before enabling derived turnover metrics.
- A `Моя работа / My work` page is available at `/my-work`, focused on the selected domain's source warnings, freshness, and published versions. Its task links remain useful for OSIP/hosted workflows; a real OIDC provider is not required for the local launcher.
- A regression fixture verifies that the spaced source columns produce real turnover, instrument mix, execution status, quantity and price values rather than the previous shifted fields.

The remaining P0 work is domain-scoped authorization, a richer mapping-preview drawer, client opening-date exception resolution, and full end-to-end verification in a Node-enabled environment.

## Implementation status — phases 1–8 foundation

The next implementation pass has now added the first cross-domain workflow controls:

- Domain scopes are separate from portfolio scopes. Development requests use `X-Actor-Domains`; OIDC can map a configured domains claim. `/api/v1/session/context` exposes the effective scopes and navigation hides unrelated domain pages.
- Non-OSIP datasets expose a reusable mapping preview at `/api/v1/dataset-versions/{id}/mapping`, including source header, sheet, row, column and sample values where the parser can prove them. In local source-first mode, incomplete mappings remain visible with DQ/unavailable fields instead of blocking the source view.
- Client opening-date exceptions remain available at `/api/v1/client-exceptions` as optional enrichment. Original `Лист6` records are immutable; manual decisions are not required for the client overview.
- Dataset and module manifests now expose parser version, generated timestamp, freshness and blocker/high DQ counts. Date mismatches remain explicit.
- Published child versions can be compared through `/api/v1/dataset-versions/{id}/compare?with_id=...`, with added/removed/changed/unchanged records and summary changes. The upload work queue exposes mapping previews and available version comparisons.
- Accounting now has a source-readiness checklist, and Risk has an explicit required-input checklist. Neither module invents official metrics without its promised source package.

The local client list shows IIN/account/document identifiers copied from the supplied workbook. Legacy OSIP routes and source downloads still retain the back-office domain scope and explicit portfolio assignment. A future hosted deployment can reintroduce masking, centralized identity, and direct-object authorization; those are not prerequisites for the local domain owner. Remaining product work is richer per-domain notifications and integration of the missing authoritative Accounting and Risk packages when supplied.
