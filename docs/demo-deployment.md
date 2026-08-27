# Shareable demo deployment

This is a lighter-weight deployment path for handing out a link to a
long-running, shared demo - it is **not** a substitute for the OIDC-based
production path in `docs/deployment-runbook.md`, and `docs/production-readiness-checklist.md`
still gates any real production release.

## What this is

- A small, fixed set of demo-persona login accounts (`demo_accounts` table),
  each scoped to one business domain the same way a real OIDC user would be
  (see `docs/domain-upload-instructions.md` for what domain scoping means).
  Logging in as one persona and confirming another domain is inaccessible is
  the actual point of the demo - it demonstrates the isolation model, not
  just the UI.
- A self-issued, short-lived session token (JWT, HS256, signed by
  `OSIP_DEMO_JWT_SECRET`) - no external identity provider to register or
  manage.
- A dataset seeded from two sources, layered: a sanitized, fully synthetic
  baseline (`services/demo_multi_source.py`) plus, on top of it, every real
  workbook in the gitignored `sources/` folder (`scripts/seed_demo_from_sources.py`
  - see "Loading everything in sources/" below). Neither ever touches the
  real `.data/local-dashboard` data - this always targets a separate
  database.

## Running it on a real server: `compose.demo.yaml`

`compose.production.yaml` (the OIDC path) is the only Compose file that
existed until 2026-08-05 - there was no equivalent one-command path for
this lighter-weight demo mode, only the manual steps below. `compose.demo.yaml`
fills that gap: same hardening as the production file (read-only
containers, dropped capabilities, `no-new-privileges`, a one-shot
`migrate` service gating startup), but with `OSIP_IDENTITY_PROVIDER=demo`
instead of OIDC, and an added one-shot `seed` service that runs
`scripts/seed_demo_accounts.py` (idempotent - safe on every restart) before
the API starts.

```bash
export OSIP_DATABASE_URL=...      # organization-managed PostgreSQL 16, not SQLite
export OSIP_DEMO_JWT_SECRET=$(openssl rand -base64 32)
export OSIP_CORS_ORIGINS='["https://your-demo-host"]'
docker compose -f compose.demo.yaml up --build -d
docker compose -f compose.demo.yaml logs seed   # first run only: capture the printed passwords now
```

Rehearsed end-to-end (real PostgreSQL 16, not SQLite) 2026-08-05: migration,
account seeding, synthetic-dataset seeding, login, and domain-isolation
(a `risk`-domain persona getting 200 on `/api/v1/risk/overview` and 403 on
`/api/v1/accounting/source-readiness`, `supervisor` getting 200 on both,
and a wrong password correctly getting 401) all confirmed working, outside
Docker specifically (this sandbox has no Docker), by running the same
image contents' code paths directly against a real local PostgreSQL
instance. The Compose file's build/run mechanics themselves (`docker
compose -f compose.demo.yaml up`) have not been run - Docker was not
available to test with - so treat the YAML as reviewed and consistent
with the already-proven-real `compose.production.yaml` pattern, not as
independently execution-tested.

To load real workbooks from `sources/` afterward, run
`scripts/seed_demo_from_sources.py` (see "Loading everything in sources/"
below) with the same `OSIP_DATABASE_URL`/`OSIP_DEMO_JWT_SECRET` against
the running deployment - it isn't part of the Compose file since it's a
one-off/as-needed operation, not something to re-run on every deploy.

## Backend configuration (manual / non-Compose)

```
OSIP_IDENTITY_PROVIDER=demo
OSIP_DEMO_JWT_SECRET=<random string, at least 32 characters>
OSIP_DATABASE_URL=<a database separate from the real local dashboard's>
OSIP_CORS_ORIGINS=["https://your-demo-host"]
```

`OSIP_DEMO_TOKEN_TTL_MINUTES` (default 1440), `OSIP_DEMO_MAX_FAILED_ATTEMPTS`
(default 8), and `OSIP_DEMO_LOCKOUT_MINUTES` (default 15) can be tuned; the
defaults are reasonable for a demo reachable over the internet for weeks.

## Seeding accounts and data

```bash
alembic upgrade head
OSIP_IDENTITY_PROVIDER=demo OSIP_DEMO_JWT_SECRET=... OSIP_DATABASE_URL=... \
  .venv/bin/python scripts/seed_demo_accounts.py
```

Safe to re-run at any time (both the account seed and the dataset seed are
idempotent). The first run prints a generated password for every persona
that doesn't have one yet - save it, only the hash is stored. Set
`OSIP_DEMO_PASSWORD_<USERNAME>` (e.g. `OSIP_DEMO_PASSWORD_ACCOUNTING`)
ahead of time to choose a password instead of generating one.

Generated passwords are 6 random alphanumeric characters (upper- and
lower-case letters plus digits, no symbols -
`_PASSWORD_ALPHABET`/`_PASSWORD_LENGTH` in
`backend/osip_dashboard/services/demo_accounts_seed.py`) - short enough to
type on a phone, with more entropy per character than a plain digit-only
code. Still not a long token: this deployment path is pre-final and meant
for handing to people to collect feedback, not a strict security boundary.
Revisit if this path is ever used for something more sensitive.

Seeded personas (`scripts/seed_demo_accounts.py`):

| username | domain | can upload? |
|---|---|---|
| `risk` | risk | yes |
| `accounting` | accounting | yes |
| `back-office` | back_office | yes |
| `client-ops` | client_ops | yes |
| `corpfin` | corpfin | yes |
| `supervisor` | all domains | no |
| `supervisor2` | all domains | no |

Every domain persona has the full upload -> approve -> publish workflow,
not just read access - each domain has exactly one owner in this
deployment, unlike a demo shared across strangers, so there's no need to
split "can view" and "can upload" into separate logins the way an earlier
version of this (`risk` + `risk-uploader`) did. `supervisor` stays
read-only: it's an all-domains observer, not a domain owner.

A retired `risk-uploader` persona from that earlier split is disabled
(not deleted) automatically the next time this script runs, if a row for
it exists.

`supervisor`'s password is always `0000`, not generated - a deliberate,
fixed exception (`_FIXED_PASSWORDS` in `scripts/seed_demo_accounts.py`),
since it's a read-only, all-domains-visible demo login with nothing
sensitive behind it worth a random password. `supervisor2` is a second,
identical all-domains observer login, added for handing out to a second
viewer at once - it gets a normal generated password like the domain
personas, not the `0000` exception. Every other persona still gets a
generated (or explicitly overridden) password as described above.

## Adding a second person to an existing domain

When a domain gets more than one owner, give the new person their own
login with a **distinct `actor_id`** - never reuse an existing persona's
`actor_id` for a second person. Per-uploader visibility
(`docs/domain-upload-instructions.md`) means whatever they upload is
scoped to their own identity, so two people sharing one `actor_id` would
each see (and be able to publish over) the other's workbooks; two people
with separate `actor_id`s each get their own private workspace within the
same domain, exactly like real production accounts would.

Add a new entry to `PERSONAS` in `scripts/seed_demo_accounts.py`, e.g. a
second Risk owner:

```python
DemoAccountSpec("risk2", "Демо: Риски (2)", "demo-risk-2", _DOMAIN_ROLES, "risk"),
```

Note this new persona will **not** see the existing seeded data (that
belongs to `_SEEDED_DATA_UPLOADER`/`e2e-uploader`) - they start with an
empty domain view until they upload their own workbook, which is the
correct, intentional behavior, not a bug to work around.

## Rotating `OSIP_DEMO_JWT_SECRET`

There's no automated rotation or expiry for this secret - it's a plain env
var, valid until someone changes it. Rotate it periodically (e.g. whenever
the demo host changes hands, or on a routine schedule if it stays up for
months) by generating a new random 32+ character value, redeploying with
it, and restarting the demo process. Rotating the secret invalidates every
outstanding session token immediately (they're stateless HS256 JWTs
verified against this one value - see `DemoIdentityProvider` in
`identity.py`), so every logged-in persona is signed out and has to log
back in; that's expected, not a bug. This doesn't touch `demo_accounts`
passwords, which are hashed and stored separately - only session tokens
are affected.

## Loading everything in sources/

**Rule: whenever `sources/` gains new or replaced files, run
`scripts/seed_demo_from_sources.py` against the demo deployment so it
reflects them.** This is the standing way real workbooks get into the demo
- never hand-guess which is which; the script's `OSIP_PORTFOLIO_FILES`
mapping is the one place that decision is recorded (legacy OSIP `.xls`
files never declare their own portfolio - see
`docs/domain-upload-instructions.md`).

```bash
OSIP_IDENTITY_PROVIDER=demo OSIP_DEMO_JWT_SECRET=... OSIP_DATABASE_URL=... \
OSIP_BLOB_ROOT=... OSIP_REFERENCE_DATA_ROOT=... \
  .venv/bin/python scripts/seed_demo_from_sources.py
```

Safe to re-run (idempotent per file - re-uploading identical bytes is a
no-op, materializing an already-active dataset is a no-op). Commits after
each file individually, not once at the end, so an interrupted run doesn't
throw away files already processed - some of these real workbooks take
tens of seconds each (thousands of formula cells to audit). A dataset that
fails the consumed-formula-audit publish gate (a real formula cell with no
valid cached result) is left `approved`-not-`published` and the script
moves on; that's a correct block, not a bug, and stays visible for review.

Real data supersedes the matching synthetic baseline dataset automatically
(`_hide_demo_versions_when_source_loaded` in `services/multi_source.py`) -
no manual cleanup needed when a real file lands for a domain the synthetic
seed already covered.

## Frontend build

```bash
docker build -f frontend/Dockerfile \
  --build-arg VITE_AUTH_MODE=demo \
  --build-arg VITE_API_BASE_URL=/api/v1 \
  .
```

No `VITE_OIDC_*` build args are required in `demo` mode.

**Building locally (not Docker), e.g. for `scripts/run_demo_deployment.py`:
always build to a separate output directory, never the default `dist/`.**
`scripts/e2e_backend.py` (the real local dashboard on port 8765, the one
behind `.data/local-dashboard`) also serves `frontend/dist` as static
files. A demo-mode build (`VITE_AUTH_MODE=demo`) written to `frontend/dist`
overwrites the real dashboard's build with one whose login flow that
dashboard's backend (`identity_provider=development`) can't serve, breaking
it outright - this happened once already. Always:

```bash
cd frontend && VITE_AUTH_MODE=demo VITE_API_BASE_URL=/api/v1 \
  npm run build -- --outDir dist-demo
```

`frontend/dist-demo/` is gitignored and is what
`scripts/run_demo_deployment.py` actually serves.
