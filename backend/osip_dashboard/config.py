"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OSIP_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://osip:osip@localhost:5432/osip"
    blob_root: Path = Path(".data/source-files")
    reference_data_root: Path = Path(".data/reference-data")
    identity_provider: Literal["development", "oidc", "demo"] = "development"
    demo_jwt_secret: str | None = None
    demo_token_ttl_minutes: int = Field(default=1440, ge=5, le=10080)
    demo_max_failed_attempts: int = Field(default=8, ge=1, le=100)
    demo_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_actor_id_claim: str = "sub"
    oidc_roles_claim: str = "roles"
    oidc_portfolios_claim: str = "portfolios"
    oidc_domains_claim: str = "domains"
    oidc_role_mapping: dict[str, Literal["uploader", "reviewer", "publisher", "reader"]] = Field(
        default_factory=dict
    )
    oidc_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    oidc_clock_skew_seconds: int = Field(default=60, ge=0, le=300)
    max_upload_bytes: int = 100 * 1024 * 1024
    risk_near_breach_threshold: float = Field(default=0.9, ge=0, lt=1)
    risk_near_breach_policy_version: str = "utilization-ratio-v1"
    # Read-only local dashboards may expose successfully parsed source data
    # immediately. Production keeps the stricter workflow unless enabled.
    source_first_mode: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @model_validator(mode="after")
    def reject_development_identity_in_production(self) -> "Settings":
        if self.environment == "production" and self.identity_provider == "development":
            raise ValueError("Production requires a non-development identity provider")
        if self.environment == "production" and not self.database_url.startswith(
            "postgresql"
        ):
            raise ValueError("Production requires PostgreSQL")
        if self.identity_provider == "demo" and (
            not self.demo_jwt_secret or len(self.demo_jwt_secret) < 32
        ):
            raise ValueError(
                "Demo identity provider requires OSIP_DEMO_JWT_SECRET set to at least 32 characters"
            )
        if self.identity_provider == "oidc":
            missing = [
                name
                for name, value in {
                    "OIDC issuer": self.oidc_issuer,
                    "OIDC audience": self.oidc_audience,
                    "OIDC JWKS URL": self.oidc_jwks_url,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError("OIDC configuration is incomplete: " + ", ".join(missing))
            if not self.oidc_role_mapping:
                raise ValueError("OIDC role mapping must be configured explicitly")
            claim_paths = {
                "actor ID": self.oidc_actor_id_claim,
                "roles": self.oidc_roles_claim,
                "portfolios": self.oidc_portfolios_claim,
                "domains": self.oidc_domains_claim,
            }
            empty_claims = [name for name, value in claim_paths.items() if not value.strip()]
            if empty_claims:
                raise ValueError(
                    "OIDC claim paths must be configured explicitly: "
                    + ", ".join(empty_claims)
                )
            if self.environment == "production":
                insecure_urls = [
                    name
                    for name, value in {
                        "OIDC issuer": self.oidc_issuer,
                        "OIDC JWKS URL": self.oidc_jwks_url,
                    }.items()
                    if value and not value.startswith("https://")
                ]
                if insecure_urls:
                    raise ValueError(
                        "Production identity endpoints must use HTTPS: "
                        + ", ".join(insecure_urls)
                    )
        if self.environment == "production" and (
            not self.cors_origins
            or any(
                origin == "*" or not origin.startswith("https://")
                for origin in self.cors_origins
            )
        ):
            raise ValueError("Production CORS origins must be explicit HTTPS origins")
        if self.environment == "production" and self.source_first_mode:
            raise ValueError(
                "Production must not enable source_first_mode - it publishes parsed "
                "data immediately, bypassing independent review and approval. It "
                "exists only for read-only local/demo dashboards."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
