"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine
from sqlalchemy import text

from osip_dashboard.api import router
from osip_dashboard.config import Settings, get_settings
from osip_dashboard.identity import (
    DemoIdentityProvider,
    DevelopmentHeaderIdentityProvider,
    IdentityProvider,
    OidcIdentityProvider,
)
from osip_dashboard.observability import install_observability
from osip_dashboard.persistence.database import create_database_engine, create_session_factory
from osip_dashboard.security import install_security_headers
from osip_dashboard.services.imports import ensure_reference_data
from osip_dashboard.services.instrument_dictionary import configure_reference_data_root
from osip_dashboard.services.dividends import configure_dividend_data_root
from osip_dashboard.storage import BlobStore, LocalBlobStore
from osip_dashboard.i18n import localize_detail, request_language


def create_app(
    *,
    settings: Settings | None = None,
    engine: Engine | None = None,
    blob_store: BlobStore | None = None,
    identity_provider: IdentityProvider | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    if settings.environment == "production" and isinstance(
        identity_provider, DevelopmentHeaderIdentityProvider
    ):
        raise ValueError(
            "Production cannot be started with the development identity provider"
        )
    engine = engine or create_database_engine(settings.database_url)
    blob_store = blob_store or LocalBlobStore(settings.blob_root)
    if identity_provider is None:
        if settings.identity_provider == "development":
            identity_provider = DevelopmentHeaderIdentityProvider()
        elif settings.identity_provider == "demo":
            identity_provider = DemoIdentityProvider(secret=settings.demo_jwt_secret or "")
        else:
            identity_provider = OidcIdentityProvider(
                issuer=settings.oidc_issuer or "",
                audience=settings.oidc_audience or "",
                jwks_url=settings.oidc_jwks_url or "",
                role_mapping=settings.oidc_role_mapping,
                actor_id_claim=settings.oidc_actor_id_claim,
                roles_claim=settings.oidc_roles_claim,
                portfolios_claim=settings.oidc_portfolios_claim,
                domains_claim=settings.oidc_domains_claim,
                algorithms=tuple(settings.oidc_algorithms),
                clock_skew_seconds=settings.oidc_clock_skew_seconds,
            )
    session_factory = create_session_factory(engine)
    configure_reference_data_root(settings.reference_data_root)
    configure_dividend_data_root(settings.reference_data_root)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        with session_factory() as session:
            ensure_reference_data(session)
            session.commit()
        yield

    app = FastAPI(
        title="Portfolio Operations Insight API",
        version="0.3.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.blob_store = blob_store
    app.state.identity_provider = identity_provider
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Actor-Id",
            "X-Actor-Roles",
            "X-Actor-Portfolios",
            "X-Actor-Domains",
            "X-Request-Id",
            "Accept-Language",
        ],
    )
    install_security_headers(app, production=settings.environment == "production")
    install_observability(app)

    @app.exception_handler(StarletteHTTPException)
    async def localized_http_exception(request: Request, exc: StarletteHTTPException):
        if request_language(request) == "en":
            exc.detail = localize_detail(exc.detail, "en")
        return await http_exception_handler(request, exc)

    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def readiness(request: Request) -> dict[str, object]:
        checks = {"database": "ok", "blob_store": "ok"}
        try:
            with request.app.state.session_factory() as session:
                session.execute(text("SELECT 1"))
        except Exception as exc:
            checks["database"] = "failed"
            raise HTTPException(
                status_code=503,
                detail={"status": "not_ready", "checks": checks, "reason": type(exc).__name__},
            ) from exc
        try:
            request.app.state.blob_store.healthcheck()
        except Exception as exc:
            checks["blob_store"] = "failed"
            raise HTTPException(
                status_code=503,
                detail={"status": "not_ready", "checks": checks, "reason": type(exc).__name__},
            ) from exc
        return {"status": "ready", "checks": checks}

    return app


app = create_app()
