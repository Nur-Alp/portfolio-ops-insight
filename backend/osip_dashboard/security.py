"""Response hardening for direct API access and private service ingress."""

from __future__ import annotations

from fastapi import FastAPI, Request


API_CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


def install_security_headers(app: FastAPI, *, production: bool) -> None:
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        if request.url.path.startswith(("/api/", "/health", "/metrics")):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = API_CONTENT_SECURITY_POLICY
        if production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
