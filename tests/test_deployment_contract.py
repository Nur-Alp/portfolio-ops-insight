from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_release_build_context_excludes_workbooks_references_and_runtime_data():
    ignored = set(_read(".dockerignore").splitlines())
    assert {"internal", "Portfolio operations", ".data", ".env", ".git"} <= ignored


def test_backend_image_is_locked_non_root_and_migration_capable():
    dockerfile = _read("Dockerfile")
    assert "python:3.12-slim-bookworm" in dockerfile
    assert "pip install --require-hashes -r requirements.lock" in dockerfile
    assert "pip install --no-deps ." in dockerfile
    assert "COPY migrations ./migrations" in dockerfile
    assert "COPY alembic.ini ./" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert 'CMD ["uvicorn"' in dockerfile
    assert "Portfolio operations" not in dockerfile


def test_frontend_release_requires_oidc_and_uses_unprivileged_ingress():
    dockerfile = _read("frontend/Dockerfile")
    assert "npm ci" in dockerfile
    # A build with VITE_AUTH_MODE=oidc must still fail without both OIDC
    # vars - only the demo build path (a separate, non-production mode; see
    # docs/demo-deployment.md) is exempt from this requirement.
    assert 'if [ "${VITE_AUTH_MODE}" = "oidc" ]; then' in dockerfile
    assert 'test -n "${VITE_OIDC_AUTHORITY}"' in dockerfile
    assert 'test -n "${VITE_OIDC_CLIENT_ID}"' in dockerfile
    assert "nginxinc/nginx-unprivileged" in dockerfile


def test_public_ingress_strips_development_identity_and_isolates_metrics():
    nginx = _read("deploy/nginx/default.conf")
    headers = _read("deploy/nginx/security-headers.inc")
    assert "location = /metrics" in nginx
    assert "return 404" in nginx
    for name in ("X-Actor-Id", "X-Actor-Roles", "X-Actor-Portfolios"):
        assert f'proxy_set_header {name} "";' in nginx
    for header in (
        "Content-Security-Policy",
        "Permissions-Policy",
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
    ):
        assert f"add_header {header}" in headers
    assert nginx.count("include /etc/nginx/conf.d/security-headers.inc;") == 3


def test_production_compose_separates_migration_and_requires_governed_identity():
    compose = _read("compose.production.yaml")
    assert "OSIP_ENVIRONMENT: production" in compose
    assert "OSIP_IDENTITY_PROVIDER: oidc" in compose
    assert "OSIP_DATABASE_URL:?" in compose
    assert 'command: ["alembic", "upgrade", "head"]' in compose
    assert "condition: service_completed_successfully" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "identity_provider: development" not in compose.lower()
