# Deployment and release runbook

This runbook packages the workbook-backed operational dashboard. It does not
authorize production release and does not change the exclusions for official
NAV, performance, accounting, trading, settlement reconciliation, or compliance.

## Deployment boundary

- The API image runs as UID/GID `10001`, contains the hash-locked Python graph,
  and does not contain either source workbook or anything under `internal/`.
- The web image is built in OIDC mode (requires `VITE_OIDC_AUTHORITY`/
  `VITE_OIDC_CLIENT_ID`) or in the lighter-weight `demo` mode (fixed,
  app-issued login accounts - see `docs/demo-deployment.md`; not a
  substitute for OIDC in an eventual production release) and runs on the
  unprivileged Nginx image at port 8080.
- Public Nginx strips every development identity header, does not expose
  `/metrics`, proxies only `/api/` and `/health/`, and serves the SPA with CSP,
  HSTS, framing, MIME, referrer, and permissions controls.
- PostgreSQL is external to `compose.production.yaml`. Use an organization-managed
  PostgreSQL 16 service with encrypted connections, backups, network policy, and
  credentials supplied by the approved secret manager.
- The shipped blob adapter is a filesystem adapter. The named volume is suitable
  for a controlled single-host deployment only. Multi-host deployment requires
  approved shared durable storage or the later S3-compatible adapter.
- TLS terminates at the organization ingress/load balancer in front of port 8080.
  Never expose the example bind directly to an untrusted network.

## Required release inputs

Do not place these values in Git or a shell-history file:

- `OSIP_DATABASE_URL`: PostgreSQL URL from the secret manager;
- exact OIDC issuer, audience, JWKS URL, actor/role/portfolio claim paths, and
  external role mapping JSON;
- exact browser OIDC authority, client ID, registered redirect URI, and scopes;
- public HTTPS origin as `OSIP_CORS_ORIGINS`, encoded as a JSON list;
- approved blob volume/storage, retention, backup, encryption, and key custody;
- release commit, image registry/repository, immutable tag, and deployment owner.

Production startup rejects SQLite, development identity, HTTP identity endpoints,
wildcard/non-HTTPS CORS, missing claim paths, missing role mapping, and symmetric
or unsigned JWT algorithms.

## Build and record artifacts

The frontend configuration is compiled into its image, so build it once for the
approved IdP client and environment. From the release commit:

```bash
docker compose -f compose.production.yaml config
docker compose -f compose.production.yaml build --pull
docker image inspect osip-portfolio-dashboard-api:local --format '{{.Id}}'
docker image inspect osip-portfolio-dashboard-web:local --format '{{.Id}}'
```

Actual Compose-generated image names depend on the project name. Push immutable
images to the approved registry, scan them, sign/attest them if required, and
record their registry digests—not local mutable image IDs—in the release record.
CI independently builds both Dockerfiles and validates the Nginx configuration.

## Pre-deployment and migration

1. Freeze workbook workflow mutations and record the current publication dates.
2. Run the full release checks and dependency/container/security scans.
3. Capture `scripts/reconcile_recovery.py --output pre-release-state.json`.
4. Create and verify an encrypted backup according to the operations runbook.
5. Review Alembic SQL and compatibility between the current and target images.
6. Run the one-shot migration and require a successful exit:

```bash
docker compose -f compose.production.yaml up --build \
  --abort-on-container-exit --exit-code-from migrate migrate
```

Do not start an API image against an unreviewed or partially migrated database.

## Start and verify

```bash
docker compose -f compose.production.yaml up -d api web
docker compose -f compose.production.yaml ps
curl --fail --silent https://APPROVED_HOST/health/live
curl --fail --silent https://APPROVED_HOST/health/ready
```

Then verify the exact commit/image digests, TLS chain, security headers, CSP with
the real IdP, OIDC login/logout/renewal, role and portfolio negatives, both source
downloads, published snapshot dates, controlled CSV, private metrics scrape, logs,
dashboards, and alert routing. Execute UAT-01 through UAT-15 and attach evidence.

## Rollback and recovery decision

- Before any data mutation, stopping the new containers and returning to the
  previous immutable images is acceptable when the prior image is compatible
  with the migrated schema.
- After imports, approvals, publication, or report generation, do not blindly
  run `alembic downgrade`: that can destroy new evidence. Freeze writes and use
  the reviewed forward fix whenever possible.
- If integrity is uncertain or the schema is incompatible, invoke the isolated,
  checksummed database/blob recovery procedure in `docs/operations-runbook.md`.
- Record the incident, decision owner, timestamps, image digests, backup identity,
  reconciliation output, and whether RPO/RTO were met.

Production deployment remains prohibited until every blocking item in
`docs/production-readiness-checklist.md` has named approval and evidence.
