"""External HTTP capacity probe helpers for production-like drills."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any


READ_PATHS = (
    "/overview",
    "/holdings?view=instruments",
    "/cash",
    "/settlements",
    "/issues",
    "/calendar",
    "/report-readiness",
)


@dataclass(frozen=True)
class ProbeSample:
    operation: str
    status_code: int
    duration_ms: float
    error: str | None = None


def summarize(samples: list[ProbeSample]) -> dict[str, Any]:
    """Return deterministic latency and error evidence for a completed run."""
    durations = sorted(sample.duration_ms for sample in samples)
    errors = [sample for sample in samples if sample.error or sample.status_code >= 400]
    count = len(samples)
    return {
        "request_count": count,
        "error_count": len(errors),
        "error_rate": len(errors) / count if count else 1.0,
        "latency_ms": {
            "p50": _percentile(durations, 0.50),
            "p95": _percentile(durations, 0.95),
            "p99": _percentile(durations, 0.99),
            "max": max(durations, default=0.0),
        },
        "status_counts": {
            str(status): sum(sample.status_code == status for sample in samples)
            for status in sorted({sample.status_code for sample in samples})
        },
        "errors": [asdict(sample) for sample in errors[:20]],
    }


def threshold_failures(
    summary: Mapping[str, Any], *, max_p95_ms: float, max_error_rate: float
) -> list[str]:
    failures: list[str] = []
    p95 = float(summary["latency_ms"]["p95"])
    error_rate = float(summary["error_rate"])
    if p95 > max_p95_ms:
        failures.append(f"p95 {p95:.3f} ms exceeds {max_p95_ms:.3f} ms")
    if error_rate > max_error_rate:
        failures.append(
            f"error rate {error_rate:.6f} exceeds {max_error_rate:.6f}"
        )
    return failures


async def run_read_probe(
    *,
    base_url: str,
    snapshot_id: str,
    headers: Mapping[str, str],
    request_count: int,
    concurrency: int,
    timeout_seconds: float,
) -> list[ProbeSample]:
    """Exercise governed snapshot reads with bounded HTTP concurrency."""
    import httpx

    semaphore = asyncio.Semaphore(concurrency)
    api_root = base_url.rstrip("/") + "/api/v1"

    async with httpx.AsyncClient(headers=dict(headers), timeout=timeout_seconds) as client:
        async def one(index: int) -> ProbeSample:
            suffix = READ_PATHS[index % len(READ_PATHS)]
            url = f"{api_root}/snapshots/{snapshot_id}{suffix}"
            async with semaphore:
                started = perf_counter()
                try:
                    response = await client.get(url)
                    duration = (perf_counter() - started) * 1000
                    error = None
                    if response.status_code == 200:
                        try:
                            response.json()
                        except ValueError:
                            error = "response is not JSON"
                    else:
                        error = response.text[:300]
                    return ProbeSample(suffix, response.status_code, duration, error)
                except Exception as exc:
                    duration = (perf_counter() - started) * 1000
                    return ProbeSample(suffix, 0, duration, type(exc).__name__)

        return list(await asyncio.gather(*(one(index) for index in range(request_count))))


async def run_idempotent_upload_probe(
    *,
    base_url: str,
    workbook: Path,
    headers: Mapping[str, str],
    concurrency: int,
    timeout_seconds: float,
    portfolio_code: str = "SOBSTV",
) -> tuple[list[ProbeSample], set[str]]:
    """Upload identical bytes concurrently and return every observed import ID."""
    import httpx

    content = workbook.read_bytes()
    url = base_url.rstrip("/") + "/api/v1/imports"
    start = asyncio.Event()
    async with httpx.AsyncClient(headers=dict(headers), timeout=timeout_seconds) as client:
        async def one(index: int) -> tuple[ProbeSample, str | None]:
            await start.wait()
            started = perf_counter()
            try:
                response = await client.post(
                    url,
                    files={"file": (workbook.name, content, "application/vnd.ms-excel")},
                    data={"portfolio_code": portfolio_code},
                )
                duration = (perf_counter() - started) * 1000
                import_id = None
                error = None
                try:
                    import_id = response.json().get("id")
                except ValueError:
                    error = "response is not JSON"
                if response.status_code not in {200, 201}:
                    error = response.text[:300]
                sample = ProbeSample(
                    f"idempotent-upload-{index}", response.status_code, duration, error
                )
                return sample, import_id
            except Exception as exc:
                duration = (perf_counter() - started) * 1000
                sample = ProbeSample(
                    f"idempotent-upload-{index}", 0, duration, type(exc).__name__
                )
                return sample, None

        tasks = [asyncio.create_task(one(index)) for index in range(concurrency)]
        start.set()
        results = await asyncio.gather(*tasks)
    return [result[0] for result in results], {
        result[1] for result in results if result[1] is not None
    }


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    rank = max(1, int(len(sorted_values) * percentile + 0.999999999))
    return round(sorted_values[min(rank, len(sorted_values)) - 1], 3)
