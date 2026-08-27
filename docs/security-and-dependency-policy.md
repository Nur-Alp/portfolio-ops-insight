# Dependency and security policy

The backend dependency graph is hash-pinned in `requirements.lock`; the frontend
graph is locked in `frontend/package-lock.json`. Application ranges remain in
`pyproject.toml` and `frontend/package.json` so intentional upgrades can be
resolved and reviewed rather than silently entering a build.

## Required update workflow

1. Change the direct dependency range deliberately.
2. Regenerate Python pins with:
   `.venv/bin/pip-compile pyproject.toml --extra dev --generate-hashes --strip-extras --allow-unsafe --output-file requirements.lock`.
3. Refresh frontend pins with `npm install` from `frontend/`.
4. Review dependency diffs, licenses, release notes, and transitive changes.
5. Run `.venv/bin/pip-audit -r requirements.lock --require-hashes` and
   `npm audit --audit-level=high`.
6. Run the backend, frontend, build, and Playwright suites before merging.

CI installs only the hash-pinned Python graph, runs both ecosystem audits, and
performs GitHub's pull-request dependency review. Dependabot proposes weekly
Python, npm, and GitHub Actions updates; it does not bypass review or tests.

## Current review baseline

On 16 July 2026, `pip-audit 2.10.1` and npm's registry audit reported no known
vulnerabilities in the resolved Python or npm graphs. This is a point-in-time
result; CI and weekly update review are the ongoing controls.

## Local domain boundary

The current product is normally launched locally by one owner of one business
domain using that owner's workbooks. The local launcher is not an internet-facing
multi-tenant deployment. Domain selection is a workspace filter, not a claim of
enterprise authorization, and client identifiers are intentionally available to
the local domain owner because they are part of the supplied source workbook.

The local mode keeps integrity controls—immutable source blobs, SHA-256
deduplication, parser/DQ findings, source lineage, version history and explicit
OSIP portfolio assignment—but does not require OIDC, central role management,
per-client masking, or four-eyes approval for read-only non-OSIP views. These
controls must be reconsidered before the app is hosted for multiple users or
connected to systems that can create downstream actions. See
[`local-domain-operating-model.md`](local-domain-operating-model.md).
