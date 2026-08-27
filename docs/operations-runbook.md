# OSIP dashboard operations runbook

> This runbook covers the controlled/hosted four-eyes workflow. The local
> domain-owner launcher uses `OSIP_SOURCE_FIRST_MODE=true`: successfully parsed
> workbooks are readable without reviewer acknowledgement, while structural
> failures and semantic DQ warnings remain visible. Do not apply the controlled
> publication-gate steps below as a prerequisite for local UAT.

This runbook covers the workbook-backed snapshot service. It does not turn the
system into official fund accounting, and it does not remove the production
release gates recorded in `docs/implementation-plan.md`.

## Service checks and telemetry

- `/health/live` proves the process event loop can answer. It has no dependency check.
- `/health/ready` runs `SELECT 1` and verifies that the local immutable blob root
  is readable and writable. Route traffic only to instances returning HTTP 200.
- `/metrics` exposes Prometheus request counts and latency histograms. Restrict it
  to the monitoring network at the ingress; it is intentionally unauthenticated
  for scrapers and contains no portfolio values or actor identities.
- Every response has `X-Request-Id`. A supplied ID is preserved; otherwise one is
  generated. Structured request logs include request ID, route template, status,
  and duration, but not workbook contents, credentials, or financial payloads.

Load `deploy/prometheus/alerts.yml` after adapting the job labels to the target
environment. Validate alert routing and paging in a non-production drill.

## Backup

Prerequisites: PostgreSQL client tools matching the server major version, enough
free space for the database plus blob archive, and `OSIP_DATABASE_URL` and
`OSIP_BLOB_ROOT` configured. Credentials are passed to PostgreSQL tools through
`PGPASSWORD`, not command arguments or the manifest.

```bash
.venv/bin/python scripts/backup.py /secure-backups/osip-YYYYMMDD-HHMMSS.tar.gz
```

The tool refuses to overwrite a destination, creates the final archive atomically,
and records SHA-256 plus size for the custom-format PostgreSQL dump and blob tar.
Because blobs are written before their database transaction commits and never
mutated, a database snapshot followed by a blob copy contains every blob referenced
by that database snapshot. New unreferenced blobs are harmless.

Copy backups to independently controlled encrypted storage. Retention, RPO, RTO,
key custody, and off-site replication are deployment-owner decisions and remain a
production gate until formally approved.

## Restore and recovery drill

Stop uploads, approvals, publications, report generation, and all API instances
before restore. Restore first in an isolated environment and reconcile portfolio,
import, snapshot, position, cash, settlement, DQ, audit, and report counts. Then:

```bash
.venv/bin/python scripts/restore.py /secure-backups/osip-YYYYMMDD-HHMMSS.tar.gz \
  --confirm-destructive-restore
alembic upgrade head
pytest -q -m postgres
```

The restore tool validates both checksums before mutation, invokes `pg_restore`
with clean/if-exists/no-owner, atomically swaps the blob root, and rolls the blob
swap back if that swap fails. The explicit flag is mandatory because the target
database and blob directory are replaced. Do not return traffic until readiness
passes and a reader verifies both portfolio publication dates and source download.

Record each recovery drill date, backup age, elapsed recovery time, reconciliation
result, operator, and corrective actions. The scripted unit tests use controlled
fake PostgreSQL commands; a real infrastructure recovery drill is still required
before production sign-off.

Capture a deterministic database/business/blob baseline immediately before the
backup, and compare the isolated restore to it after `alembic upgrade head`:

```bash
.venv/bin/python scripts/reconcile_recovery.py --output pre-backup-state.json
.venv/bin/python scripts/backup.py /secure-backups/osip-drill.tar.gz
# Restore into the isolated target, then point OSIP_DATABASE_URL/OSIP_BLOB_ROOT at it.
.venv/bin/python scripts/reconcile_recovery.py \
  --baseline pre-backup-state.json \
  --output restored-state.json
```

The comparison validates table counts, every snapshot’s governed totals and
status, and the SHA-256/size of each source and report artifact. It exits nonzero
for a missing/corrupt blob or any state difference. Attach both JSON files, the
backup manifest, elapsed time, PostgreSQL version, storage encryption evidence,
and source-download screenshots to UAT-14.

## API unavailable or readiness failing

1. Confirm whether liveness, database, or blob storage is failing.
2. Correlate the `X-Request-Id` with structured logs; do not paste workbook data into tickets.
3. Check PostgreSQL connectivity, capacity, locks, migrations, and credentials.
4. Check blob mount presence, permissions, capacity, and filesystem errors.
5. Keep the instance out of rotation until readiness is stable for five minutes.
6. If integrity is uncertain, freeze workflow mutations and begin the verified recovery procedure.

## Elevated server errors or latency

1. Break down `osip_http_requests_total` by route template and status.
2. Inspect p95 latency by route without creating actor/import-ID cardinality.
3. Check PostgreSQL slow queries, connection exhaustion, disk pressure, and concurrent imports.
4. Preserve failed imports and audit events; never delete evidence as remediation.
5. If synchronous parsing breaches the tested workload, pause uploads and move
   parsing to a durable worker in a planned change rather than raising limits live.

## Workbook import or DQ incident

1. Confirm the original hash and exact source download remain available.
2. Review parser version, failed-state evidence, DQ codes, and prior-version comparison.
3. Do not acknowledge blocker/high findings without documented reviewer justification.
4. Upload corrections as immutable new versions; never edit or replace stored evidence.
5. Publish SOBSTV and TABYS independently and expose report-date mismatch.

## Current performance envelope

Synchronous parsing is approved only for the current two source files, each below
200 KiB, with a 10 MiB hard upload rejection boundary. CI parses the two golden
workbooks twenty times within a conservative ten-second budget. This is a regression
guard, not a future capacity promise. Re-test with production-like concurrency and
the largest approved workbook before changing file-size or volume assumptions.

## Production-like capacity drill

Agree the concurrency, request volume, p95 target, error-rate target, database
size, CPU/memory limits, and largest approved workbook before running the drill.
Run it against the release image, PostgreSQL 16, production-equivalent ingress,
OIDC, and monitoring—not against an in-process test client. For example:

```bash
.venv/bin/python scripts/capacity_probe.py \
  --base-url https://osip-uat.example.com \
  --snapshot-id REPLACE_WITH_PUBLISHED_SNAPSHOT_UUID \
  --requests 1000 \
  --concurrency 25 \
  --max-p95-ms 1000 \
  --max-error-rate 0.001 \
  --bearer-token "$OSIP_UAT_ACCESS_TOKEN" \
  --output capacity-evidence.json
```

In a disposable non-production environment, add
`--idempotent-upload-workbook path/to/source.xls` to send identical uploads at
the configured concurrency and prove they all resolve to one import ID. Never
place tokens in the evidence file or command history. Attach the JSON, service
metrics, PostgreSQL metrics, image digest, environment sizing, and alert results
to UAT-13. The script exits nonzero when an agreed threshold or idempotency check
fails; a passing local or SQLite run is not production-like evidence.
