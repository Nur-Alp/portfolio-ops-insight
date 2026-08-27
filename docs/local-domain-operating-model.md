# Local domain operating model

**Status:** current product decision, 21 July 2026

## Why the model changed

Portfolio Operations Insight is currently run locally by the person responsible for one
business domain. That person supplies the domain's workbooks and uses the app to
turn those workbooks into a clear operational overview. It is not currently a
shared internet-facing, multi-tenant system and it does not send trades,
payments, accounting entries, client notifications, or risk decisions to a
downstream system.

The workbook is therefore the authoritative source for the domain's available
facts. The app should preserve, parse, display, compare, and cite those facts;
it should not make the owner confirm every client or publish a value as if it
were an official NAV or accounting result.

## Domain is the primary workspace

The main operating context is one domain:

| Domain | Owner | Current source boundary |
|---|---|---|
| `back_office` | Бэк офис | OSIP, TABYS valuation and unit-history workbooks |
| `client_ops` | Клиентский / Brokerage | client, account, trade and derivative workbooks |
| `corpfin` | Корпфин | corporate-finance register workbook |
| `accounting` | Бухгалтерия | landing/DQ evidence until the complete accounting package arrives |
| `risk` | Risk manager | placeholder until the risk source package arrives |

The local top-bar domain selector is a workspace filter and navigation aid, not
an enterprise identity boundary. A domain owner should normally select one
domain and see that domain's pages, uploads, warnings, exports, and source
manifest without configuring portfolio-level permissions.

## Controls kept because they protect data integrity

These controls remain useful even in a local, low-risk deployment:

- the original workbook is retained unchanged under its SHA-256 content key;
- a corrected workbook creates a new version rather than overwriting history;
- parser failures, unsupported files, schema changes, formula errors, and date
  mismatches remain visible as DQ findings;
- every displayed row retains workbook/sheet/row provenance;
- source, derived, and unavailable values remain clearly labelled;
- OSIP portfolio assignment remains explicit because assigning a workbook to the
  wrong portfolio can mislead the overview even without a downstream write;
- withdrawal/replacement is reversible and retains the original evidence;
- local `.data/` files remain outside Git and should be backed up only if the
  owner needs local history to survive a machine failure.

These are data-quality and recoverability controls, not access bureaucracy.

## Controls relaxed for the local mode

For all source types in the local demo, `OSIP_SOURCE_FIRST_MODE=true` means a
successfully parsed source becomes readable immediately. This is a trusted
source presentation mode: the supplied workbook is assumed to be the best
available record for that domain, even when sensitive/redacted fields produce
semantic warnings. The following are informational or optional rather than
publication blockers:

- four-eyes reviewer/publisher approval;
- acknowledgement of every blocker/high DQ code before the overview is shown;
- manual client-name/account matching;
- field-mapping confirmation when the source row can still be displayed with an
  unavailable field;
- a separate reader/uploader/publisher persona for the same local operator;
- portfolio-level authorization inside a single-owner domain workspace;
- masking IIN, account, and document identifiers in the client table.

This does **not** mean that every file is accepted. The importer still rejects
empty files, temporary/system files, unsupported formats, invalid OLE/OOXML
signatures, missing required headers, unreadable workbooks, parser failures,
and values that cannot be represented safely. Those are structural or
processing failures, not business-data disagreements. Once the workbook parses,
content DQ findings (missing prices, date mismatches, formula errors preserved
as unavailable, ambiguous labels, and similar observations) are retained with
their workbook/sheet/row evidence and shown as warnings. They do not require
manual acknowledgements in local mode and do not prevent an operational export.

The optional identity-resolution API remains available for a future workflow,
but it is enrichment only. The workbook's client/account rows are usable without
resolving the opening-date reference file.

OSIP imports retain explicit portfolio assignment because a local operator can
still select the wrong portfolio code and make a misleading view. In local
source-first mode a structurally valid OSIP workbook is published automatically
after that explicit assignment; the controlled four-eyes/DQ acknowledgement
workflow remains the default whenever `OSIP_SOURCE_FIRST_MODE` is disabled.

## What is not being removed

Local mode does not make the app an official accounting, NAV, performance, risk,
or transaction system. It does not invent absent values, repair source formulas,
silently fuzzy-match clients, or write back to a workbook or external service.
The UI continues to disclose operational/derived status and source dates.

The OIDC provider, signed claims, role mapping, portfolio permissions, and
production security checklist remain in the codebase as a future deployment
boundary. They are not prerequisites for the current local-domain workflow and
should not be presented as required setup for a domain owner running the local
`.command` launcher.

## Local operator checklist

1. Start the local launcher.
2. Choose the responsible domain in the top bar.
3. Upload the workbook supplied for that domain.
4. Check the source date, parsed totals, DQ warnings, and source references.
5. Use the pages and Excel exports directly; no per-client confirmation is
   required.
6. If a workbook was assigned to the wrong OSIP portfolio, withdraw that view
   and upload it again with the correct explicit portfolio code.

For a domain-specific `.command` launcher, set `VITE_DOMAIN_SCOPE` before the
frontend build. This pins the initial selector to the responsible domain while
leaving the selector available for local testing.

If the application is later hosted for multiple users or begins writing to
external systems, revisit this decision and re-enable centralized identity,
least-privilege roles, masking, independent approval, and direct-object access
tests before exposing it outside the local machine.
