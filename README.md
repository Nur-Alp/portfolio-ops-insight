# Portfolio Operations Insight

Controlled multi-source analytics and reporting for Portfolio Operations Insight. The application combines OSIP portfolio snapshots with independently versioned fund valuation/history, brokerage/client, corporate-finance, risk-limit and accounting-landing feeds. It deliberately does not invent official NAV/performance, accounting results, VaR, stress, capital-adequacy, or risk-appetite metrics when the authoritative source is absent.

## Quick start (no terminal, no setup)

If you just want to open the dashboard and look around, this is the only section you need.

For someone who does not have Git or does not know how to use it, send them **`get-dashboard.command`** (macOS) or **`get-dashboard.bat`** (Windows). They double-click that one file; it downloads the repository into `Downloads/portfolio-operations-dashboard` (using a GitHub ZIP when Git is unavailable) and starts the dashboard.

1. Download or clone this repository to your computer.
2. Make sure **Python 3.11 or newer** is installed. If you're not sure, install it from [python.org/downloads](https://www.python.org/downloads/) — on Windows, check "Add python.exe to PATH" during install.
3. Open the project folder and **double-click**:
   - **`start-dashboard.command`** on macOS (first time, right-click it and choose "Open" instead, since it isn't code-signed — macOS will ask you to confirm once).
   - **`start-dashboard.bat`** on Windows.
4. A window opens showing progress. The first run installs a few things automatically and can take a minute; every run after that is a few seconds. Your browser opens to the dashboard automatically when it's ready. After a successful launch, the temporary launcher window closes automatically; the dashboard continues running in the background. The same applies to the stop launcher. If an operation fails, its window stays open so you can read the error.
5. When you're done, double-click **`stop-dashboard.command`** / **`stop-dashboard.bat`** to shut it down (optional — it doesn't do anything in the background if you just close the window).

This starts a local, self-contained copy pre-loaded with the two supplied OSIP workbooks plus generated, sanitized examples for the new business modules. No real client source is copied into the demo database or Git. It doesn't need PostgreSQL, Docker, Node.js, or a login, and it doesn't touch anything outside this folder.

If something goes wrong, see [Startup troubleshooting](#startup-troubleshooting) below, or check `.data/local-dashboard/server.log`.

For a dependency-only check, run `python scripts/launch.py diagnose` from the project folder. It reports the Python version, virtual-environment/pip support, packaged frontend, write permissions, and local port availability without starting the dashboard.

Everything past this point is for developers changing the code, not for viewing the dashboard.

## What is implemented

- Immutable physical `source_uploads` with content-based type detection and independently publishable child dataset versions. Filenames are evidence only.
- Adapters for TABYS valuation/holdings/cash-liabilities/NAV history/prices, TABYS and SAQ unit-value history, brokerage trades/derivatives/client accounts/opening dates, corporate-finance mandates, SOBSTV/TABYS risk-limit controls, and accounting landing/DQ evidence.
- Cross-source fund reconciliations with explicit date-mismatch status, plus source manifests on every new domain read model.
- Portfolio Operations Insight navigation for Corporate finance, Brokerage, Clients, Asset management, Treasury, Risk and limits, Operations and reconciliations, DQ, uploads, reporting, and an explicit Accounting pending-source page.
- Russian-formatted XLSX exports for published fund, brokerage, client and corporate-finance data. Client-detail reads and exports are audited without placing account/IIN values in URLs, logs or audit parameters.
- FastAPI HTTP API with PostgreSQL 16 as the deployment database and SQLite only for isolated tests.
- A domain-oriented work queue integrated into `Операции и сверки / Operations and reconciliations` at `/operations`, with source warnings, freshness, review and publication actions. The former `/my-work` URL redirects there. The local domain selector is the primary workspace boundary; centralized portfolio/role claims are a future hosting concern.
- Non-OSIP datasets expose a source mapping preview at `/api/v1/dataset-versions/{id}/mapping`, optional identity enrichment at `/api/v1/client-exceptions`, freshness/provenance manifests, and version comparison at `/api/v1/dataset-versions/{id}/compare?with_id=...`.
- Detected source uploads are domain-scoped before materialization; the local source-first demo shows parsed domain data immediately. Client identifiers are visible to the local domain owner because the workbook is their supplied source; no data is sent to downstream systems.
- In the local development demo, the top-bar domain selector switches the workspace between all domains, Back Office, Client Operations, Corporate Finance, Accounting, and Risk. Production OIDC domain claims remain available only for a future hosted deployment.
- Accounting includes an explicit source-readiness checklist; no official metrics are invented before its authoritative source package arrives. Risk parses and publishes SOBSTV/TABYS investment-limit controls (country, currency, open FX position, issuer, sector, instrument category, duration, IFRS) directly from source workbooks, with a visible staleness warning when a source is old; VaR, stress, capital-adequacy and risk-appetite metrics remain unavailable since no authoritative model/source exists for them.
- Accounting's source-readiness page participates in the same historical-version workflow as the other domain pages: when published or superseded `accounting_*` child datasets exist, operators can inspect the source manifest and pin a specific version; pinning never turns landing evidence into accounting metrics. Risk exposes separate version selectors for the independently scheduled SOBSTV and TABYS risk-limit workbooks, so one side can be reviewed historically without silently replacing the other.
- SQLAlchemy 2 persistence and an Alembic baseline migration.
- Immutable, SHA-256-addressed original files under ignored `.data/source-files/` storage.
- Parser-independent ORM records for portfolios, imports, snapshots, individual position lots, cash, raw source rows, deduplicated settlements, DQ findings/acknowledgements, and audit events.
- Idempotent re-upload by source hash within the assigned portfolio; corrected content becomes a new version for the same portfolio/report date. A withdrawn misassignment may be uploaded unchanged under the correct portfolio code.
- Workflow states `draft → validating → validated → approved → published`, plus terminal `failed`, `rejected`, `superseded`, and `withdrawn` states.
- Strict four-eyes approval remains available for controlled OSIP/hosted workflows. Local non-OSIP source-first views do not require reviewer/publisher clicks; DQ findings stay visible and are not silently corrected.
- A publisher can remove an erroneous published version from operational dashboard reads with a mandatory reason; the source workbook, snapshot, and audit trail are retained and marked `withdrawn` rather than deleted.
- Independent SOBSTV and TABYS publication. `GET /api/v1/portfolios` explicitly reports the published report dates and whether they mismatch.
- Published snapshot APIs with ISO dates, decimal strings, source-row lineage, retained lots, and `source` / `derived` / `unavailable` metric bases.
- Local identity headers and the domain selector are convenience workspace controls, not a security boundary. Signed OIDC, role-claim mapping, and portfolio-level permissions remain a future hosted-deployment option.

Source-reported TABYS NAV is labelled as source/manual rather than accounting-approved official NAV. OSIP values remain `operational/derived`. Complete accounting functionality, and risk VaR/stress/capital-adequacy metrics, remain unavailable until their authoritative packages arrive; Risk's source-backed investment-limit controls are implemented.

Accounting landing workbooks are date-conservative: maturity, coupon, opening and
other date-shaped cells are retained as sheet evidence but never determine a
dataset's report/business date. Those dates are populated only when the workbook
explicitly labels a report date; otherwise the source-readiness view shows the
date as unavailable. This prevents a future maturity (for example, 2028) from
being mistaken for the latest accounting reporting date.

The Client/Brokerage trade adapter resolves `Лист8` by header text rather than
spacer-column positions. This prevents prices from appearing as execution
statuses and exposes a mapping-confidence DQ gate before a low-confidence trade
ledger can be approved.

The same workbook also publishes `client_maturity_calendar` from
`календарь погашения`. Client subtotal rows (`Итого`, `ВСЕГО`) are retained only
as workbook evidence and are excluded from client totals. The Clients page
shows the source maturity events and manager distribution; the Brokerage page
uses the actual `Лист7` derivatives fields. Corporate Finance normalizes ISINs
even when the source writes labels such as `ISINXS...`, while preserving the
original free-text subject. The cached `Клиенты` summary is a separate source
dataset; when its totals differ from `Лист4`, the discrepancy remains visible
as DQ and the account-register totals remain the KPI basis.

## Developer quick reference

If you're changing code rather than just viewing the dashboard, see the
[Quick start](#quick-start-no-terminal-no-setup) above for the simplest way to
view it, or use these directly:

| Task | Address | Command |
|---|---|---|
| View the populated dashboard | `http://127.0.0.1:8765` | `.venv/bin/python scripts/demo_service.py start` |
| Run the development API | `http://127.0.0.1:8000/docs` | `uvicorn osip_dashboard.main:app --reload` |
| Run the development frontend | `http://127.0.0.1:5173` | `cd frontend && npm run dev` |

`frontend/dist/` is committed and prebuilt, so the demo above never requires
Node.js — only rebuild it (`cd frontend && npm run build`) after changing
frontend source. Prerequisites for the rest of this document:

- Python 3.12 for the CI-equivalent environment and release images;
- Node.js 22 and npm only for building or developing the frontend;
- Docker Desktop only for the local PostgreSQL development service;
- the supplied `.xls` workbooks must remain in `Portfolio operations/` for the
  local demo and browser end-to-end suite.

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.lock
pip install --no-deps -e .
cp .env.example .env
docker compose up -d postgres
alembic upgrade head
uvicorn osip_dashboard.main:app --reload
```

For a reproducible CI-equivalent environment, install the reviewed lock before
the editable project: `pip install --require-hashes -r requirements.lock`, then
`pip install --no-deps -e .`.

API documentation is then available at `http://127.0.0.1:8000/docs`. Run all local tests with:

```bash
pytest -q
```

The stable machine-readable client contract is committed at
[`docs/openapi.json`](docs/openapi.json). Route declarations are grouped under
`backend/osip_dashboard/routes/`, while `api_schemas.py` owns the versioned
request/response models. After an intentional API change, regenerate and review
the contract with `.venv/bin/python scripts/export_openapi.py`.
The frontend contract is generated from that artifact at
`frontend/src/api/schema.d.ts`; run `npm run api:generate` after an intentional
API change. CI regenerates it and fails on drift, while application aliases in
`frontend/src/api/types.ts` reference generated schemas rather than duplicating
response interfaces by hand. The request layer uses those generated paths through
`openapi-fetch`, so route names, path/query parameters, request bodies, and
responses are checked during the strict TypeScript build.

The React/TypeScript frontend is under `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

It runs at `http://127.0.0.1:5173` and proxies API requests to the FastAPI service.

Run `./scripts/install_git_hooks.sh` once to make `git push` run the same
checks CI runs (`pytest -q`, `npm run api:check`, `tsc -b`, `vitest run`)
before anything leaves your machine - this catches the most common cause of
a red CI run (an unregenerated `docs/openapi.json` / `schema.d.ts` after an
API change) locally instead of several minutes later on GitHub. It does not
run the Playwright E2E suite, whose visual-regression check is inherently
CI-only (see `update-e2e-snapshots` in `.github/workflows/ci.yml`); run
`npm run test:e2e` by hand before a UI-visible change if you want that
coverage first. Bypass once with `git push --no-verify`.

Keep the API terminal running while using the development frontend. The
development application requires PostgreSQL and initializes the empty
portfolio reference data on its first startup; unlike the demo, it does not
automatically import or publish the supplied workbooks.

## View the dashboard demo

The quickest way to inspect the working dashboard is to start its local demo
environment. It imports and publishes the two supplied OSIP workbooks and adds
generated sanitized examples for the new modules into an ignored local database;
it does not read the ignored real `sources/` directory, change tracked project data, or require a
login. Manual uploads and their version history survive service restarts. The
server has no inactivity timeout. If it was started by an assistant,
browser test, or temporary command environment, that environment can still end
the process; use the service controller below from your own terminal when you
want it to remain available.

The persistent local demo runs all domain uploads in source-first mode:
successfully parsed client, brokerage, fund, corporate-finance, and OSIP
datasets become readable immediately after the explicit OSIP portfolio
assignment. DQ findings and source references remain visible, but they are
warnings rather than publication gates in this local, source-authoritative
mode. Structural checks still reject unreadable or incompatible workbooks.

`frontend/dist/` is committed, so no frontend build is needed on a fresh
clone. Only rebuild it if you changed frontend source:

```bash
cd "$(git rev-parse --show-toplevel)/frontend"
npm install
npm run build
```

Start the persistent local dashboard from the repository root. This keeps a
real, persistent database under `.data/local-dashboard/` - back it up before
any risky local experiment; it is not disposable test data.

```bash
.venv/bin/python scripts/demo_service.py start
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765). The service runs in a
detached local process, so it remains available after that command and terminal
exit. Its PID, database, source files, and log are stored only in ignored
`.data/local-dashboard/`.

Useful commands:

```bash
.venv/bin/python scripts/demo_service.py status
.venv/bin/python scripts/demo_service.py restart
.venv/bin/python scripts/demo_service.py stop
```

Back up the real local database before any risky experiment (safe to run
while the dashboard is running):

```bash
.venv/bin/python scripts/backup_local_dashboard.py
```

Snapshots land in ignored `.data/local-dashboard/backups/`; the 10 most
recent are kept by default (`--keep N` to change that).

To use another free port, pass it consistently to the start command and browser:

```bash
.venv/bin/python scripts/demo_service.py start --port 8768
```

The script serves the built frontend and API together, so no second terminal is
needed. This is a local convenience tool, not production process supervision.

The frontend unit, build, and live browser checks are:

```bash
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The browser suite uses a disposable local database and blob store, publishes both
workbooks through the real application services, and leaves no project data behind.

The latest persistent-demo database and web projection audit is documented in
[Database and web audit — 21 July 2026](docs/database-web-audit-2026-07-21.md).

The page-by-page feature audit and current implementation decisions are documented in
[Page and feature audit — 21 July 2026](docs/page-feature-audit-2026-07-21.md).

The page/widget/chart lineage check is documented in
[Data provenance audit — 21 July 2026](docs/data-provenance-audit-2026-07-21.md).
It records the integrity, lineage, workflow, calculation, API and route checks,
as well as the remaining launcher health-detection bug and the limits of local
SQLite evidence.

All Excel-export generators should follow the reusable
[Excel export design standards](docs/excel-export-design-standards.md), covering
units, provenance, formulas, navigation, language, and validation.

The role-to-workbook and reference-dictionary upload matrix is in
[Domain upload instructions](docs/domain-upload-instructions.md).

[Risk and Accounting Phase 2 groundwork](docs/phase-2-groundwork-risk-accounting.md)
records the parser/API evidence, source-period constraints, reconciliation
prerequisites, and validation plan before those features are implemented.

The executed clean-database import and domain UAT evidence is recorded in
[UAT execution record — 21 July 2026](docs/uat-execution-2026-07-21.md).
It lists the verified source totals and the DQ decisions still required from
the Back Office, Client Operations and Corporate Finance owners.

The role-by-role operating workflow and UI plan for Бухгалтерия, Бэк офис,
Клиентский, Корпфин and Risk is documented in
[Role workflows and UI plan — 21 July 2026](docs/role-workflows-ui-plan-2026-07-21.md).
It maps each supplied workbook to its owner, records current data limitations,
and defines the independent upload, DQ, review and publication flow as of that
date; risk-manager sources have since arrived and Risk is now implemented.
The additional accounting package remains a prerequisite for its full page.

## Startup troubleshooting

### macOS says the file can't be opened / is from an unidentified developer

Right-click `start-dashboard.command` and choose **Open**, then confirm in the
dialog that appears. This is only needed the first time, since the script
isn't code-signed.

### Double-clicking `start-dashboard.bat` does nothing / closes instantly

Open a Command Prompt, `cd` into the project folder, and run
`start-dashboard.bat` from there so the error message stays visible. This
usually means Python isn't installed or wasn't added to PATH — reinstall from
[python.org/downloads](https://www.python.org/downloads/) with "Add python.exe
to PATH" checked.

### Port already in use

Choose a free demo port and open the matching URL:

```bash
.venv/bin/python scripts/demo_service.py start --port 8768
```

Then open `http://127.0.0.1:8768`. Stop it with
`.venv/bin/python scripts/demo_service.py stop`.

### Browser says `ERR_CONNECTION_REFUSED`

Nothing is listening on the address shown in the browser. From the repository
root, check and restart the local demo:

```bash
.venv/bin/python scripts/demo_service.py status
.venv/bin/python scripts/demo_service.py restart
```

If restart reports a startup failure, read `.data/local-dashboard/server.log`.

Known limitation: the current local controller considers a PID alive without
also checking the recorded HTTP port or `/health`. Consequently, `status` can
occasionally report that the demo is running when the process is stale or no
longer serving requests. Treat the browser and `http://127.0.0.1:8765/health`
as the availability check until the controller's process/health validation is
hardened. Do not manually signal a PID from `.data/local-dashboard/server.json`
without first confirming that it belongs to this dashboard.

### `npm: command not found`

Install Node.js 22, open a new terminal, and confirm `node --version` and
`npm --version` work. Then run `npm install` from `frontend/` before `npm run
build` or `npm run dev`.

### GitHub Actions fails at `pip install --require-hashes`

CI, the backend release image, and the frontend job all use the same
`requirements.lock`. Regenerate that lock with Python 3.12 whenever Python
dependencies change; do not manually add a package line or remove hash mode:

```bash
source .venv/bin/activate
python -m pip install pip-tools
pip-compile --allow-unsafe --extra=dev --generate-hashes \
  --output-file=requirements.lock --strip-extras pyproject.toml
pip install --require-hashes -r requirements.lock
pytest -q
```

The generated lock must contain every transitive package as an exact,
hash-pinned entry. For example, SQLAlchemy's `greenlet` dependency must be
pinned; an unpinned `greenlet>=1` error means the lock needs regeneration.

## Release containers

`Dockerfile` packages the non-root FastAPI/Alembic runtime, while
`frontend/Dockerfile` produces an OIDC-only unprivileged Nginx image. The root
`.dockerignore` excludes the real workbooks, ignored references, local data, and
developer secrets from both build contexts. `compose.production.yaml` is a
single-host release template with a separate migration job; it deliberately
requires an external PostgreSQL 16 database and approved production configuration.

Build, migration, security-header, TLS/ingress, verification, and rollback steps
are in [`docs/deployment-runbook.md`](docs/deployment-runbook.md). This definition
does not replace organization infrastructure review or production sign-off.

PostgreSQL integration tests run automatically in GitHub Actions. Locally, point them to a disposable PostgreSQL database:

```bash
OSIP_TEST_POSTGRES_URL=postgresql+psycopg://osip:osip@localhost:5432/osip_test pytest -m postgres
```

## Local domain operator

The normal local workflow has one responsible operator per domain. Choose the
domain in the top bar; that selection controls which domain pages and source
uploads are shown. The local API still accepts `X-Actor-Id`,
`X-Actor-Roles`, `X-Actor-Portfolios`, and `X-Actor-Domains` so automated tests
and controlled OSIP workflows remain reproducible, but these headers are not
intended to model enterprise authorization for the local launcher.

To make a domain-specific launcher open on one domain by default, set
`VITE_DOMAIN_SCOPE` to one of `back_office`, `client_ops`, `corpfin`,
`accounting`, or `risk` before building the frontend. The operator can still
switch domains from the top bar; the setting only chooses the initial view.

For local domain workbooks, the persistent demo enables source-first mode:
successful parsing makes the dataset readable immediately. Client identity
matching and reviewer/publisher actions are optional. The original workbook,
source references, DQ findings, and version history remain available. A DQ
finding never rewrites the source or becomes an invented zero; it is displayed
as an evidence-backed warning. Hosted
production deployments may later replace this local model with signed OIDC
claims and least-privilege roles; that is not required for the local app.

Shared pages such as Operations, Data quality, and Source uploads use
only the datasets visible to the selected domain. They do not make an OSIP
portfolio or metric-catalogue request when a non-Back-Office domain is active,
so a Corporate Finance, Client Operations, Accounting, or Risk operator can
open them without a misleading “no access to back_office” error. The OSIP
portfolio filter and controlled OSIP report are shown only for Back Office (or
the all-domains workspace); OSIP data itself is unchanged.

Example upload:

```bash
curl -F 'file=@Portfolio operations/your-file.xls' \
  -F 'portfolio_code=YOUR_PORTFOLIO_CODE' \
  -F 'portfolio_name=Display name for a new portfolio' \
  -H 'X-Actor-Id: uploader-1' \
  -H 'X-Actor-Roles: uploader,reader' \
  http://127.0.0.1:8000/api/v1/imports
```

## API surface

Import workflow:

- `POST /api/v1/imports`
- `GET /api/v1/imports`
- `GET /api/v1/imports/{id}`
- `GET /api/v1/imports/{id}/source`
- `POST /api/v1/imports/{id}/approve`
- `POST /api/v1/imports/{id}/reject`
- `POST /api/v1/imports/{id}/publish`

Dashboard reads:

- `GET /api/v1/portfolios`
- `GET /api/v1/portfolios/{code}/snapshots`
- `GET /api/v1/snapshots/{id}/overview`
- `GET /api/v1/snapshots/{id}/holdings`
- `GET /api/v1/snapshots/{id}/cash`
- `GET /api/v1/snapshots/{id}/settlements`
- `GET /api/v1/snapshots/{id}/issues`

Default portfolio snapshot lists expose only published versions. Use `include_unpublished=true` for authorized operational inspection. Direct snapshot reads are also operational inspection endpoints and still require the `reader` role.

## Workbook contract

Business rows are never selected by fixed row number. The parser discovers the header through stable labels in columns A, G, H, and Q, then classifies all later rows:

- current position lot: column H populated and column Q positive;
- settlement event: column H populated and column Q negative, except rows under
  the `Предстоящие расчеты` section, which are deliberately excluded from all
  imports, calendar events, totals, and DQ checks;
- cash balance: column A starts with `ОСТАТОК ДЕНЕЖНЫХ СРЕДСТВ`;
- otherwise, populated column A becomes the current source section.

Inserted and reordered rows are supported while columns remain intact. Column movement, deletion, or renaming is a schema-contract failure. Every imported business row is retained as JSON with workbook, sheet, row number, and parser version lineage. Settlement deduplication never discards either raw source reference.

### Portfolio identity and unreliable filenames

OSIP workbooks do not contain a stable, unique portfolio identifier: their
visible and `Temp` metadata can use the same generic portfolio name across
different portfolios. The filename is therefore **evidence only**. It is stored
unchanged with the source hash, but it is never used to determine the portfolio
or validate the report date.

During upload, the responsible manager supplies a canonical portfolio code.
Existing codes are reused; a new valid code creates a portfolio record with the
optional supplied display name. The report date is read from the workbook
metadata, and the upload may proceed with any `.xls` filename. This makes stale
or system-generated export filenames safe while preserving the exact original
file for audit.

This is an assignment control, not an automated guess: a manager must not
assign a workbook to a portfolio based only on overlapping instruments. For
production, approve a portfolio registry, restrict who may create new codes,
and require a second-person review of a first upload or an unexpected portfolio
assignment.

The transparent operational carrying-value formula is `AA × AU × AT + AR`. It is stored as derived data and must not be presented as official NAV or market value.

## Storage and production boundary

`BlobStore` isolates content storage; this stage ships the local content-addressed adapter only. An S3-compatible implementation can replace it later without changing import/workflow contracts. `.data/` is ignored by Git and must be backed up according to the deployment retention policy.

Production rejects development identity. Set `OSIP_ENVIRONMENT=production` with
`OSIP_IDENTITY_PROVIDER=oidc`, issuer, audience, JWKS URL, claim paths, and an
explicit external-to-application role mapping. The API validates signature,
issuer, audience, time claims, and configured asymmetric algorithms. The browser
uses OIDC authorization code with PKCE and never sends development impersonation
headers in OIDC mode. IdP client registration, approved redirect URIs, exact claim
contract, group assignment, key rotation, and organization sign-off are still
required before exposure.

Additional analysis, the captured functionality template, and `port-acc` feasibility notes live under the Git-ignored `internal/` directory for local project context. The tracked, comprehensive mapping of Portfolio Operations Insight demo capabilities to the missing OSIP data, controls, and implementation work is in [`docs/product-feature-gap-register.md`](docs/product-feature-gap-register.md).

A maintained inventory of every implemented feature is in
[`docs/feature-inventory.md`](docs/feature-inventory.md) — update it in the same
change whenever a feature is added, changed, or removed.

The tracked phase-by-phase delivery status is maintained in [`docs/implementation-plan.md`](docs/implementation-plan.md).
Dependency locking and audit procedures are in
[`docs/security-and-dependency-policy.md`](docs/security-and-dependency-policy.md).
Health checks, metrics, alert rules, backup/restore, and incident procedures are
documented in [`docs/operations-runbook.md`](docs/operations-runbook.md).
The same runbook includes a threshold-enforcing external capacity probe for the
required production-like PostgreSQL/ingress/identity drill.
Release evidence and external approvals are driven by the
[`docs/uat-and-reconciliation-plan.md`](docs/uat-and-reconciliation-plan.md) and
[`docs/production-readiness-checklist.md`](docs/production-readiness-checklist.md).

The single consolidated backlog — open engineering items, the production-readiness
path, product-scope gaps, and open product decisions, each indexed back to its
source doc rather than duplicated — is [`docs/todo.md`](docs/todo.md).
