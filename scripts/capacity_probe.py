"""Run OSIP production-like read and idempotent-upload capacity probes."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

from osip_dashboard.operations.capacity import (
    run_idempotent_upload_probe,
    run_read_probe,
    summarize,
    threshold_failures,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure the deployed OSIP API and emit reviewable JSON evidence."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=float, default=30)
    parser.add_argument("--max-p95-ms", type=float, required=True)
    parser.add_argument("--max-error-rate", type=float, required=True)
    parser.add_argument("--bearer-token")
    parser.add_argument("--actor-id", default="capacity-probe")
    parser.add_argument("--actor-roles", default="reader,uploader")
    parser.add_argument("--actor-portfolios", default="*")
    parser.add_argument(
        "--idempotent-upload-workbook",
        type=Path,
        help="In a non-production environment, concurrently upload identical bytes.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")
    if not 0 <= args.max_error_rate <= 1:
        parser.error("--max-error-rate must be between zero and one")
    return args


async def _run(args: argparse.Namespace) -> tuple[dict[str, object], list[str]]:
    headers = (
        {"Authorization": f"Bearer {args.bearer_token}"}
        if args.bearer_token
        else {
            "X-Actor-Id": args.actor_id,
            "X-Actor-Roles": args.actor_roles,
            "X-Actor-Portfolios": args.actor_portfolios,
        }
    )
    samples = await run_read_probe(
        base_url=args.base_url,
        snapshot_id=args.snapshot_id,
        headers=headers,
        request_count=args.requests,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout_seconds,
    )
    read_summary = summarize(samples)
    failures = threshold_failures(
        read_summary,
        max_p95_ms=args.max_p95_ms,
        max_error_rate=args.max_error_rate,
    )
    evidence: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "target": args.base_url,
        "snapshot_id": args.snapshot_id,
        "configuration": {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "timeout_seconds": args.timeout_seconds,
            "max_p95_ms": args.max_p95_ms,
            "max_error_rate": args.max_error_rate,
            "authentication": "bearer" if args.bearer_token else "development headers",
        },
        "reads": read_summary,
    }
    if args.idempotent_upload_workbook:
        upload_samples, import_ids = await run_idempotent_upload_probe(
            base_url=args.base_url,
            workbook=args.idempotent_upload_workbook,
            headers=headers,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout_seconds,
        )
        upload_summary = summarize(upload_samples)
        upload_summary["observed_import_ids"] = sorted(import_ids)
        upload_summary["idempotent"] = len(import_ids) == 1
        evidence["idempotent_upload"] = upload_summary
        failures.extend(
            threshold_failures(
                upload_summary,
                max_p95_ms=args.max_p95_ms,
                max_error_rate=args.max_error_rate,
            )
        )
        if len(import_ids) != 1:
            failures.append(
                f"identical concurrent uploads returned {len(import_ids)} import IDs"
            )
    evidence["result"] = "pass" if not failures else "fail"
    evidence["failures"] = failures
    return evidence, failures


def main() -> None:
    args = _arguments()
    evidence, failures = asyncio.run(_run(args))
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
