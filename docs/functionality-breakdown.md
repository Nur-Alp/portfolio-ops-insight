# OSIP Portfolio Dashboard — functionality breakdown

A plain-language guide to what the application actually does today, written
from the current API routes and frontend pages rather than from plans. For
delivery status and acceptance evidence, see
[implementation-plan.md](implementation-plan.md) and
[requirements-traceability.md](requirements-traceability.md).

**Current operating model:** the app is normally run locally by the owner of
one domain using that domain's own workbooks. See
[local-domain-operating-model.md](local-domain-operating-model.md). The stricter
reviewer/publisher and OIDC controls described below remain available for OSIP
or a future hosted deployment; local non-OSIP source-first views do not require
them.

## What this application is

It turns legacy OSIP and domain workbooks into an auditable, versioned dashboard.
Local non-OSIP sources follow: upload → parse → source-first browse. OSIP keeps
explicit portfolio assignment and can use the controlled upload workflow. Every
displayed number remains traceable to the exact source row it came from.

It does **not** calculate official NAV or performance, and it does not read
from or write to `port-acc`. Figures are explicitly labeled `source`,
`derived`, or `unavailable` — a broken workbook formula is shown as
unavailable, never silently defaulted to zero.

## Roles and access

| Role | Can do |
|---|---|
| `uploader` | Upload a workbook to create a new import |
| `reviewer` | Approve or reject a validated import (four-eyes: cannot approve their own upload) |
| `publisher` | Publish an independently approved import |
| `reader` | List imports, download source evidence, browse published snapshots and reports |

Locally, roles come from `X-Actor-Id` / `X-Actor-Roles` headers, optionally
scoped to specific portfolios via `X-Actor-Portfolios`. In production, the
same roles and portfolio scope come from a signed OIDC token's claims — the
development header path is rejected outright when
`OSIP_ENVIRONMENT=production`.

## Import and publication workflow (`/imports`)

The **Загрузки источников / Imports** page and its API:

- **Upload** a `.xls` workbook. The file is hashed (SHA-256) and stored
  immutably; the filename is kept as evidence but never used to infer the
  portfolio or report date — those are read from the workbook content and
  assigned by the uploader.
- **Idempotent re-upload**: uploading byte-identical content returns the
  existing import rather than duplicating it. A corrected file becomes a new
  version of the same portfolio/report date.
- **State machine**: `draft → validating → validated → approved → published`,
  with terminal `failed`, `rejected`, and `superseded` states. Rejected and
  failed imports are kept, not deleted, so evidence is never lost.
- **Compare** an import against the prior approved version before deciding.
- **Approve / reject**: requires a different actor than the uploader
  (four-eyes), and a mandatory justification. Any blocker- or high-severity
  data-quality finding must be explicitly acknowledged before approval.
- **Publish**: controlled/hosted OSIP deployments use a separate,
  publisher-only step from approval. The local `OSIP_SOURCE_FIRST_MODE`
  deployment publishes a structurally valid assigned workbook immediately;
  DQ findings remain visible warnings. SOBSTV and TABYS publish independently,
  and the portfolio list explicitly reports when their published report dates
  don't match.
- **Download** the exact original workbook behind any import, at any time,
  for audit.

## Portfolio catalogue (`/portfolios`, `/metrics`)

- Lists governed portfolios with their latest published report date, and
  flags a mismatch if SOBSTV and TABYS are on different dates.
- Lists governed metric definitions — which figures are supported, and on
  what basis (source vs. derived) — so the frontend can show a metric as
  unavailable rather than compute something ungoverned.
- Lists a portfolio's snapshot history (every published version over time).

## Overview page (`/`)

The landing page for a published portfolio version:

- Portfolio-level totals with their metric basis (source / derived /
  unavailable) and the report date and version they belong to.
- Portfolio structure/allocation, switchable between purchase-amount and
  derived-carrying-value basis, aggregated by instrument while keeping the
  link down to individual lots.
- Version-control panel: publication status and data-quality gate state.
- A short in-page glossary explaining how to read the figures.

## Holdings page (`/holdings`)

- Instrument-level aggregation of current positions.
- Drill-down drawer per instrument, opening into the underlying **immutable
  position lots** — the individual source rows that were summed, each
  traceable back to its workbook row.

## Cash & calendar page (`/cash-calendar`)

- Cash balances per custodian, in source currency and KZT-equivalent, with
  an option to reveal zero-balance template rows from the workbook.
- A currency summary (explicitly labeled as not an independently reconciled
  bank position).
- A calendar of dated events at the lot level — redemptions, coupons, repo
  dates — sourced from the workbook. The OSIP "upcoming settlements" section
  is deliberately excluded from this calendar and handled separately.

## Data quality page (`/data-quality`)

- Every data-quality finding tied to its rule, severity, the fields it
  affects, its source location in the workbook, and its acknowledgement
  status — searchable and filterable by severity.
- A list of governed metrics that are only shown when both their source data
  and calculation methodology support them.

## Reporting page (`/reporting`)

- Shows whether a published portfolio version is ready to export, and what
  is gating it if not.
- Generates a controlled **report run**: an immutable, versioned export
  package (workbook evidence, canonical data, DQ findings, approval
  identity) — explicitly framed as an approved package, not an ad hoc
  export. Report classes can be individually available or unavailable
  depending on policy.
- Every artifact retains the publication identity (who approved/published,
  version) that produced it.

## Snapshot read APIs behind the pages

`/snapshots/{id}/overview`, `/holdings`, `/allocations`, `/cash`,
`/settlements`, `/issues`, `/calendar`, `/report-readiness` — all read-only,
all scoped to one published (or, for authorized operational inspection,
unpublished) snapshot version, and all `reader`-role gated.

## Settlement handling

Raw settlement rows from the workbook are deduplicated exactly (10 raw
SOBSTV rows collapse to 5, for example) without discarding either original
source reference — both raw rows remain linked in the lineage.

## What's deliberately out of scope right now

- Official NAV / performance calculation.
- Any read or write path into `port-acc`.
- Data entry or editing — the dashboard is read/govern-only over workbook
  imports.
