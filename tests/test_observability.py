from fastapi.testclient import TestClient

from osip_dashboard.config import Settings
from osip_dashboard.main import create_app
from osip_dashboard.persistence import Base
from osip_dashboard.persistence.database import create_database_engine
from osip_dashboard.storage import LocalBlobStore


def test_liveness_readiness_request_identity_and_metrics(api):
    request_id = "trace-test-001"
    live = api.get("/health/live", headers={"X-Request-Id": request_id})
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert live.headers["X-Request-Id"] == request_id
    assert live.headers["X-Content-Type-Options"] == "nosniff"
    assert live.headers["X-Frame-Options"] == "DENY"
    assert live.headers["Referrer-Policy"] == "no-referrer"
    assert live.headers["Cache-Control"] == "no-store"
    assert live.headers["Content-Security-Policy"] == (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    assert "Strict-Transport-Security" not in live.headers

    ready = api.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "checks": {"database": "ok", "blob_store": "ok"},
    }

    metrics = api.get("/metrics")
    assert metrics.status_code == 200
    assert "osip_http_requests_total" in metrics.text
    assert 'route="/health/live"' in metrics.text
    assert "osip_http_request_duration_seconds" in metrics.text


def test_readiness_reports_dependency_failure_without_exposing_details(api):
    original = api.app.state.blob_store

    class UnavailableBlobStore:
        def healthcheck(self):
            raise OSError("sensitive infrastructure detail")

    api.app.state.blob_store = UnavailableBlobStore()
    try:
        response = api.get("/health/ready")
    finally:
        api.app.state.blob_store = original

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "status": "not_ready",
        "checks": {"database": "ok", "blob_store": "failed"},
        "reason": "OSError",
    }
    assert "sensitive infrastructure detail" not in response.text


def test_production_responses_add_hsts_without_constructing_development_identity(
    tmp_path,
):
    database_url = f"sqlite:///{tmp_path / 'security.sqlite3'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://unused:unused@database/osip",
        blob_root=tmp_path / "blobs",
        identity_provider="oidc",
        oidc_issuer="https://identity.example/tenant",
        oidc_audience="osip-api",
        oidc_jwks_url="https://identity.example/keys",
        oidc_role_mapping={"finance-reader": "reader"},
        cors_origins=["https://osip.example"],
    )

    class UnusedProductionIdentity:
        def actor_from_request(self, _request):
            raise AssertionError("Health check must not resolve an actor")

    app = create_app(
        settings=settings,
        engine=engine,
        blob_store=LocalBlobStore(settings.blob_root),
        identity_provider=UnusedProductionIdentity(),
    )
    with TestClient(app) as client:
        response = client.get("/health/live")
    engine.dispose()

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == (
        "max-age=31536000; includeSubDomains"
    )
