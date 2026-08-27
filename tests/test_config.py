import pytest
from pydantic import ValidationError

from osip_dashboard.config import Settings
from osip_dashboard.identity import DevelopmentHeaderIdentityProvider
from osip_dashboard.main import create_app


def test_production_rejects_development_identity_provider():
    with pytest.raises(ValidationError, match="non-development identity provider"):
        Settings(environment="production", identity_provider="development")


def test_demo_identity_provider_requires_a_sufficiently_long_secret():
    with pytest.raises(ValidationError, match="OSIP_DEMO_JWT_SECRET"):
        Settings(identity_provider="demo")
    with pytest.raises(ValidationError, match="OSIP_DEMO_JWT_SECRET"):
        Settings(identity_provider="demo", demo_jwt_secret="too-short")

    settings = Settings(identity_provider="demo", demo_jwt_secret="x" * 32)
    assert settings.identity_provider == "demo"


def test_production_oidc_requires_complete_explicit_claim_mapping():
    with pytest.raises(ValidationError, match="OIDC configuration is incomplete"):
        Settings(environment="production", identity_provider="oidc")
    with pytest.raises(ValidationError, match="role mapping"):
        Settings(
            environment="production",
            identity_provider="oidc",
            oidc_issuer="https://identity.example/tenant",
            oidc_audience="osip-api",
            oidc_jwks_url="https://identity.example/tenant/keys",
        )

    settings = Settings(
        environment="production",
        identity_provider="oidc",
        oidc_issuer="https://identity.example/tenant",
        oidc_audience="osip-api",
        oidc_jwks_url="https://identity.example/tenant/keys",
        oidc_role_mapping={"finance-reader": "reader"},
        cors_origins=["https://osip.example"],
    )
    assert settings.identity_provider == "oidc"


def test_production_rejects_explicit_development_identity_injection():
    settings = Settings(
        environment="production",
        identity_provider="oidc",
        oidc_issuer="https://identity.example/tenant",
        oidc_audience="osip-api",
        oidc_jwks_url="https://identity.example/keys",
        oidc_role_mapping={"finance-reader": "reader"},
        cors_origins=["https://osip.example"],
    )
    with pytest.raises(ValueError, match="development identity provider"):
        create_app(
            settings=settings,
            identity_provider=DevelopmentHeaderIdentityProvider(),
        )


def test_production_requires_postgresql_and_explicit_claim_paths():
    common = {
        "environment": "production",
        "identity_provider": "oidc",
        "oidc_issuer": "https://identity.example/tenant",
        "oidc_audience": "osip-api",
        "oidc_jwks_url": "https://identity.example/keys",
        "oidc_role_mapping": {"finance-reader": "reader"},
        "cors_origins": ["https://osip.example"],
    }
    with pytest.raises(ValidationError, match="requires PostgreSQL"):
        Settings(**common, database_url="sqlite:///production.db")
    with pytest.raises(ValidationError, match="claim paths"):
        Settings(**common, oidc_portfolios_claim="   ")


def test_production_requires_https_identity_and_cors_boundaries():
    common = {
        "environment": "production",
        "identity_provider": "oidc",
        "oidc_issuer": "https://identity.example/tenant",
        "oidc_audience": "osip-api",
        "oidc_jwks_url": "https://identity.example/keys",
        "oidc_role_mapping": {"finance-reader": "reader"},
        "cors_origins": ["https://osip.example"],
    }
    with pytest.raises(ValidationError, match="identity endpoints must use HTTPS"):
        Settings(**{**common, "oidc_issuer": "http://identity.example/tenant"})
    with pytest.raises(ValidationError, match="CORS origins"):
        Settings(**{**common, "cors_origins": ["*"]})
    with pytest.raises(ValidationError, match="CORS origins"):
        Settings(**{**common, "cors_origins": ["http://osip.example"]})


def test_production_rejects_source_first_mode():
    common = {
        "environment": "production",
        "identity_provider": "oidc",
        "oidc_issuer": "https://identity.example/tenant",
        "oidc_audience": "osip-api",
        "oidc_jwks_url": "https://identity.example/keys",
        "oidc_role_mapping": {"finance-reader": "reader"},
        "cors_origins": ["https://osip.example"],
    }
    with pytest.raises(ValidationError, match="source_first_mode"):
        Settings(**common, source_first_mode=True)
    # A non-production environment may still use it - that's the local/demo case.
    settings = Settings(environment="development", source_first_mode=True)
    assert settings.source_first_mode is True
