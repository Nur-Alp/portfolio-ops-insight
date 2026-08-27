# OSIP Portfolio Dashboard — реестр функциональных разрывов Portfolio Operations Insight

**Статус:** канонический технический источник для будущих сессий Codex и планирования продукта.  
**Дата:** 20 июля 2026 г.  
**Сопроводительный документ:** `internal/OSIP_PortfolioOpsInsight_реестр_функциональных_разрывов.docx` (для участников проекта).

## Назначение и границы

Этот документ фиксирует, что потребуется для реализации в OSIP Portfolio Dashboard каждой публично видимой функции Portfolio Operations Insight demo, которой нет или которая реализована лишь частично в текущей версии.

Основания анализа:

- 14 из 14 маршрутов Portfolio Operations Insight, 196 captured UI-состояний и interaction audit от 16 июля 2026 г.;
- `internal/functionality-template/functionality-report.md`;
- `internal/osip-workbook-dashboard-readiness-analysis.md`;
- `internal/osip-portfolio-dashboard-feasibility-and-delivery-plan.md`;
- текущая кодовая база OSIP.

Демо-сайт является функциональным и визуальным ориентиром. Его public build не доказывает наличие production backend, реальных интеграций, устойчивых прав доступа, сохранения данных или официальных расчётов. Нельзя переносить demo KPI в OSIP без авторитетных источников и методологии.

## Текущая база OSIP

Уже реализовано:

- content-based импорт OSIP `.xls`, исходный файл по SHA-256, immutable import evidence и tolerant parsing строк при сохранении контракта колонок;
- snapshots, position lots, cash balances, source rows, DQ issues и audit events;
- workflow `draft → validating → validated → approved → published`, независимое approval и снятие ошибочной публикации без удаления evidence;
- русскоязычные страницы: обзор портфеля, holdings/lots, деньги и календарь, качество данных, загрузки и отчётность;
- базовая lineage до файла/листа/строки, Source/Derived/Unavailable labels, DQ acknowledgement/owner/due date;
- governed CSV operational snapshot.

Ограничения, которые нельзя обходить UI-расчётами:

- официальный NAV, market value, доходность и P&L недоступны;
- текущая расчётная балансовая стоимость — operational derived metric, а не NAV и не рыночная стоимость;
- текущие workbooks не являются полноценными transaction, settlement, cash или client ledgers;
- раздел OSIP `Предстоящие расчеты` исключён из импорта, календаря, итогов и DQ по утверждённому правилу продукта.

## Приоритеты

| Метка | Значение |
|---|---|
| P0 | Обязательный фундамент, без которого портфельные/операционные функции будут недостоверны. |
| P1 | Следующее расширение после P0: history, workflow, reports, clients/fees при подтверждённом scope. |
| P2 | Enterprise-модуль: требует самостоятельного product decision, владельца и новых системных контуров. |

## Общие функции приложения

| Функция Portfolio Operations Insight | Состояние OSIP | Что требуется |
|---|---|---|
| Command search / `⌘K` | Нет | permission-aware search index по портфелям, инструментам, импортам, отчётам и cases; keyboard navigation. |
| Общие filters: период, entity, business line, currency, role | Частично: portfolio/date/currency/basis | canonical dimensions, единый URL-state contract, selectors с учётом прав. |
| Production RBAC / ABAC | Частично: local roles и OIDC interface | IdP onboarding, portfolio/entity entitlements, masking, segregation of duties, audit доступа. |
| Уведомления и inbox | Нет | event bus, preferences, email/Teams adapters, escalation и delivery log. |
| RU/KZ/EN | Частично: RU | i18n catalogue, metric glossary, locale/date/number tests и translated templates. |
| Настоящий export | Частично: CSV | XLSX/PDF jobs, template engine, download audit, archive/hash, watermark/entitlements. |
| Saved views | Частично: URL filters | сохранённые filter snapshots, owner/shared scope и permission checks. |
| Единый design system | Частично | reusable components, accessibility, responsive policy, visual regression и Russian microcopy glossary. |

## Реестр по маршрутам демо

### 1. Центр управления — `/dashboard`

Отсутствуют:

- group KPIs: чистая/базовая прибыль, операционный доход, cost-to-income, план/факт;
- P&L waterfall, revenue mix, contribution by business line и related-party split;
- корпоративные signals/action register, регуляторные отчёты и управленческие AI observations.

Требуются: GL и management P&L, план/бюджет, entity hierarchy, правила консолидации, period-close calendar, metric service, action registry, owners/SLA/notifications и каталог отчётов. Это P2, если OSIP остаётся портфельным продуктом; не следует строить как побочный эффект workbook import.

### 2. Финансовый результат — `/finance`

Отсутствуют IFRS/Management/Core views, reported-to-underlying bridge, rolling forecast, expense analytics, balance и Income-vs-OpEx drawers.

Требуются: IFRS ledger, management adjustments, chart-of-accounts mapping, budget versions, forecast model, cost centres, owner comments, source-level finance lineage и close process. Это P2 enterprise finance module.

### 3. Корпоративные финансы / сделки — `/deals`

Отсутствуют pipeline, Kanban, mandate creation, fee forecast, weighted fees, coverage plan, win rate, cycle time и deal economics.

Требуются: CRM/deal master, stages/history, client/participants, probability, deal budget/costs, fees, tasks, documents, approvals и integration with CRM/ECM. Это P2 и отдельный product scope; demo Create Deal не демонстрировал server persistence.

### 4. Комиссии и дебиторка — `/fees`

Отсутствуют recognised/billed/collected fees, invoice ledger, receivables aging, overdue/disputed invoices, DSO, cash conversion и reminders.

Требуются: fee accrual subledger, invoice/payment records, due dates, client/entity master, dispute/collections workflow, GL linkage и notification service. OSIP workbook содержит только acquisition fees по лотам, а не invoice lifecycle. P1 при включении billing scope.

### 5. Брокерская деятельность — `/brokerage`

Отсутствуют AuC, turnover, commissions, yield, active-client cohorts, NNA, KASE position, venue/instrument mix, client/RM economics и opportunities.

Требуются: customer accounts, daily positions/NAV, trades, cash flows, commission ledger, execution/venue feed, affiliation dimension, RM assignment и CRM data. Это P1/P2 и требует client-level entitlements; текущий OSIP — собственный portfolio snapshot, не брокерский ledger.

### 6. Клиенты — `/clients`

Отсутствуют account funnel, funding/activation metrics, segment/region/channel/RM filters, inactive-client risk, client assets/NNA и client drawer.

Требуются: client/account master, onboarding/funding/activity event logs, client-level holdings/cash flows, segmentation/scoring rules, RM model, privacy/consent controls, ABAC/masking и audit access. P1.

### 7. Управление активами — `/asset-management`

Частично существует только portfolio inventory. Отсутствуют официальный AUM/NAV, performance/benchmark, subscriptions/redemptions/net flow, fee estimate и полноценные Performance/Flows/Portfolio/Fees tabs.

Требуются:

- approved valuation/NAV history, liabilities, pricing hierarchy, price/FX source and timestamp, valuation approvals;
- investor/unit register, subscriptions/redemptions/distributions, transfer-agent status and cut-off;
- benchmark total-return series, external flows и утверждённая TWR/MWR methodology;
- fee schedules, accrual/billing rules и payment state.

Official NAV/performance — P0/P1 data dependency; их нельзя заменять current derived carrying value.

### 8. Казначейство — `/treasury`

Уже есть holdings/cash/calendar и derived carrying value. Отсутствуют market/book/risk-weighted valuation basis, interest income/yield/return/unrealised P&L, duration/liquidity, historical composition и instrument impact explanation (carry/duration/FX).

Требуются official valuation feed, historical positions, income/corporate-action ledger, transaction ledger, instrument cash-flow schedules, curves, liquidity haircuts/market-depth data, factor mapping и calculation service. Market/book is P0; duration/sensitivity is P2.

### 9. Риски и лимиты — `/risk`

Отсутствуют CAR, capital/liquidity buffers, open FX position, VaR 1d 99%, stress loss, risk appetite matrix, limits, breaches, owners, next review и scenarios USD +10% / Rates +200 bp / Equities −15% / Combined.

Минимальные требования:

- capital/RWA/liabilities/liquidity ladder и regulatory formula governance;
- account-level FX and exposures;
- instrument cash flows, curves, duration/convexity, risk factors, historical returns, volatilities/correlations;
- approved scenario definitions, model versioning, validation/backtesting;
- limit catalogue with scope, threshold, effective dates, severity, owner, exception workflow and audit.

Простая concentration exposure может быть derived из holdings после instrument-master normalization, но не должна выдавать себя за полноценный risk framework. Полный модуль — P2.

### 10. Операции и сверки — `/operations`

Отсутствуют order/STP/settlement KPIs, lifecycle, settlement trend, reconciliation matrix, breaks, break case drawer и month-end close checklist.

Требуются:

- orders, allocations, executions and settlements с external IDs, timestamps и state transitions;
- expected/actual cash and security legs, counterparty/custodian confirmations, fail reason;
- bank/custodian statements и matching/reconciliation engine;
- case management: comments, evidence, owner, SLA, remediation action, closure validation;
- close calendar/checklists/sign-offs/escalations.

Это P0 для реального operational platform. Current calendar не является settlement reconciliation, а `Предстоящие расчеты` исключены из OSIP scope.

### 11. KYC / AML — `/compliance`

Отсутствуют KYC throughput, SLA aging, periodic reviews, sanctions/PEP alerts, escalations, case register и investigation drawer.

Требуются client/person/entity master, KYC risk rating, review schedules, screening-provider results, match/disposition history, false-positive rationale, case workflow, evidence/documents и strict restricted access. Это P1 отдельного compliance domain с legal/privacy/retention governance.

### 12. Фабрика отчётности — `/reporting`

Частично реализованы snapshot readiness, validation gates, versions и operational CSV. Отсутствуют due/ready/blocked/overdue register, owner/calendar/search, full report drawer (Overview/Sources/Controls/Narrative/Versions/Submission), PDF/XLSX templates и submission receipts.

Требуются report catalogue, reporting calendar, report instances/status/SLA, template and rendering service, source snapshotting, narrative editor/approval, immutable artifact archive/hash, distribution and submission adapters. P1. Official/regulatory reports требуют approved official sources и signatory rules.

### 13. Качество данных — `/data-quality`

Частично есть DQ rules/issues, severity, acknowledgements, ownership/due date и source-row lineage. Отсутствуют DQ score, completeness/timeliness/reconciliation dimensions, source-health/stale sources, domain/owner filters, metric graph (Overview/Lineage/DQ/Usage) и полный remediation workflow.

Требуются source registry, ingestion monitor, data freshness SLA, rule catalogue and scheduler, score methodology, business glossary, transformation/usage lineage graph, action state machine, comments/evidence/notifications и independent closure controls. P1.

### 14. AI-аналитик — `/ai-analyst`

Отсутствуют morning briefing, material changes, structured question/answer flow, saved analytics и source-linked chart/DQ context. Demo implementation был deterministic и работал на embedded demo data; это не готовый AI backend.

Нужны curated governed metric/event layer, change-detection rules, source citations, structured response schema (observation/driver/effect/action/confidence/guardrails), RAG/semantic retrieval over approved sources, prompt/model version audit, permission-aware context, evaluation tests, human escalation и monitoring. Только P2 после reliable metrics, lineage и DQ.

## Наборы данных и интеграции

| Приоритет | Набор | Минимальный контракт | Что разблокирует |
|---|---|---|---|
| P0 | Portfolio/account/custodian master | IDs, legal owner, base currency, mandate, active dates, hierarchy | portfolio identity, account reporting, entitlements |
| P0 | Instrument master | instrument/issuer IDs, ISIN, class, subtype, currency, sector, coupon/maturity/day count | classification, joins, coupons, risk mapping |
| P0 | Official valuation & FX | clean/dirty price, source/time, price type, approval, FX source/time, accrued interest | market value/NAV/P&L readiness |
| P0 | Transaction/execution ledger | order/execution IDs, side, trade/settlement dates, quantity, price, gross/net, fees, counterparty, venue, status | turnover, P&L, lifecycle |
| P0 | Settlement & cash ledgers | cash/security legs, expected/actual values, currency, status, fail reason, bank/custodian evidence | reconciliation, liquidity, operations |
| P1 | Historical NAV/position and flows | dated positions/NAV/liabilities, subscriptions/redemptions/distributions, benchmark | performance, AUM, trends, flows |
| P1 | Income/corporate actions/ratings | event IDs, ex/record/pay, gross/net/tax, agency/outlook/effective date | income, corporate actions, rating risk |
| P1 | Clients/CRM/invoices/KYC | clients/accounts/RM, invoices/payments, onboarding/reviews, screening cases | brokerage, clients, AR, compliance |
| P2 | Risk data and limit governance | cash flows, curves, factors, volatility/correlation, models, limits/exceptions | VaR, stress, duration, limit monitoring |

## Системные компоненты

1. **Integration gateway** — API/SFTP/file ingestion, schema registry, retries, quarantine, idempotency и freshness monitoring.
2. **Canonical operational store** — masters, ledgers, snapshots и immutable evidence. Current OSIP snapshot layer является началом, не заменой ledgers.
3. **Calculation and valuation service** — versioned formulas, Decimal math, calendars, pricing/risk inputs, reproducible run records.
4. **Workflow/case management** — owners, comments, evidence, SLA, approvals, notifications, closure controls и audit.
5. **Reporting service** — templates, jobs, source snapshotting, validation gates, rendered artifacts, archive и submission receipts.
6. **Data catalogue/lineage** — glossary, metric definitions, source-to-field mapping, transformations, DQ impact и usage graph.
7. **Security platform** — production OIDC, ABAC, segregation of duties, masking, export controls и audit review.
8. **Observability/support** — health, data freshness, job logs, errors, capacity, backup/restore tests и runbooks.

## Рекомендуемая последовательность delivery

1. **Scope and governance:** решить, остаётся ли продукт portfolio/operations dashboard или становится multi-business Portfolio Operations Insight platform; назначить data owners и KPI owners.
2. **P0 data foundation:** portfolio/account/instrument masters, valuation, transaction, settlement and cash contracts; integrations и data-quality gates.
3. **Portfolio and treasury operations:** historical snapshots, official valuation readiness, settlement/cash lifecycle, reconciliation exceptions, richer governed reporting.
4. **Performance, flows, clients and fees:** только если scope включает fund administration, investors или brokerage.
5. **Risk, limits, compliance and advanced reporting:** после models, policies, independent validation и security controls.
6. **AI analyst:** только поверх governed metrics, lineage, DQ, permissions и report readiness.

## Критерии готовности любой новой функции

- Есть business definition, owner, frequency, authoritative source и explicit unavailable state.
- Source contract содержит durable IDs, timestamps, freshness/SLA, ownership и record-level lineage.
- Calculation versioned, tested, reconciled и сохраняет run/version/source inputs.
- UI показывает source/derived/unavailable basis, reporting date, version и evidence; не показывает zero вместо missing.
- Write/action path имеет RBAC/ABAC, maker-checker where required, reason, audit event и rollback/support procedure.
- Export/submission сохраняет immutable artifact/hash, payload identity, actor/time и validation result.
- UAT включает positive/negative/DQ scenarios и sign-off владельца процесса.

## Открытые решения владельца продукта

- Какие демо-модули действительно входят в OSIP scope: Finance, Deals, Brokerage, Clients, KYC/AML — или это отдельные продукты?
- Какой первый официальный показатель должен появиться: NAV, market value, AUM или другой? Кто утверждает методологию?
- Какие системы будут systems of record для master data, valuation, trading, settlements/cash, clients, limits и reports?
- Требуются ли regulatory submissions в первом target release или сначала internal operational reporting?
- Какие privacy, data residency, masking и export controls применяются к client-level/KYC data?
- Какой refresh cadence нужен по каждому домену: intraday, EOD, T+1, month-end?

## Правило для будущих Codex-сессий

При реализации функции из списка сначала найти в этом документе её data dependencies и governance prerequisites. Не добавлять KPI, risk result, NAV, performance, reconciliation или client/compliance workflow как UI-only simulation. Если требуемого authoritative source нет, отображать функцию как `Недоступно` с причиной и создавайте отдельный data onboarding work package.
