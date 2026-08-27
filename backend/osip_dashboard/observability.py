"""Low-cardinality HTTP telemetry and structured request logging."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


LOGGER = logging.getLogger("osip_dashboard.requests")
REQUESTS = Counter(
    "osip_http_requests_total",
    "HTTP requests handled by the OSIP API.",
    ("method", "route", "status"),
)
REQUEST_DURATION = Histogram(
    "osip_http_request_duration_seconds",
    "OSIP HTTP request duration in seconds.",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


def install_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def observe_request(request: Request, call_next):
        started = perf_counter()
        request_id = request.headers.get("X-Request-Id") or str(uuid4())
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            elapsed = perf_counter() - started
            route_object = request.scope.get("route")
            route = getattr(route_object, "path", "unmatched")
            REQUESTS.labels(request.method, route, str(status)).inc()
            REQUEST_DURATION.labels(request.method, route).observe(elapsed)
            LOGGER.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "route": route,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 3),
                    },
                    separators=(",", ":"),
                )
            )

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
