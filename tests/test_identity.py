from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from osip_dashboard.identity import DemoIdentityProvider, OidcIdentityProvider
from osip_dashboard.services.workflow import Actor


ISSUER = "https://identity.example/tenant"
AUDIENCE = "osip-api"


def _token(private_key, **overrides):
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-123",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "realm_access": {"roles": ["finance-reader", "unmapped-role"]},
        "osip_portfolios": ["SOBSTV"],
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def test_oidc_validates_signature_standard_claims_and_explicit_mappings(api):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider = OidcIdentityProvider(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://unused.example/keys",
        role_mapping={"finance-reader": "reader"},
        roles_claim="realm_access.roles",
        portfolios_claim="osip_portfolios",
        domains_claim="osip_domains",
        key_resolver=lambda _token: private_key.public_key(),
    )
    original = api.app.state.identity_provider
    api.app.state.identity_provider = provider
    try:
        no_token = api.get("/api/v1/portfolios")
        assert no_token.status_code == 401
        assert no_token.headers["WWW-Authenticate"] == "Bearer"

        valid = api.get(
            "/api/v1/portfolios",
            headers={"Authorization": f"Bearer {_token(private_key)}"},
        )
        assert valid.status_code == 200
        assert [item["code"] for item in valid.json()["items"]] == ["SOBSTV"]

        context = api.get(
            "/api/v1/session/context",
            headers={"Authorization": f"Bearer {_token(private_key, osip_domains=['back_office'])}"},
        )
        assert context.status_code == 200
        assert context.json()["domains"] == ["back_office"]

        denied = api.get(
            "/api/v1/portfolios/TABYS/snapshots",
            headers={"Authorization": f"Bearer {_token(private_key)}"},
        )
        assert denied.status_code == 403

        both_portfolios = api.get(
            "/api/v1/portfolios",
            headers={
                "Authorization": f"Bearer {_token(private_key, osip_portfolios=['SOBSTV', 'TABYS'])}"
            },
        )
        assert [item["code"] for item in both_portfolios.json()["items"]] == [
            "SOBSTV",
            "TABYS",
        ]

        no_portfolio = api.get(
            "/api/v1/portfolios",
            headers={
                "Authorization": f"Bearer {_token(private_key, osip_portfolios=[])}"
            },
        )
        assert no_portfolio.status_code == 200
        assert no_portfolio.json()["items"] == []

        unmapped_role = api.get(
            "/api/v1/portfolios",
            headers={
                "Authorization": f"Bearer {_token(private_key, realm_access={'roles': ['unmapped-role']})}"
            },
        )
        assert unmapped_role.status_code == 403

        wrong_audience = api.get(
            "/api/v1/portfolios",
            headers={
                "Authorization": f"Bearer {_token(private_key, aud='another-api')}"
            },
        )
        assert wrong_audience.status_code == 401
        assert wrong_audience.json()["detail"] == "Bearer-токен недействителен"

        wrong_issuer = api.get(
            "/api/v1/portfolios",
            headers={
                "Authorization": f"Bearer {_token(private_key, iss='https://identity.example/other')}"
            },
        )
        assert wrong_issuer.status_code == 401

        expired = api.get(
            "/api/v1/portfolios",
            headers={
                "Authorization": f"Bearer {_token(private_key, exp=datetime.now(UTC) - timedelta(minutes=5))}"
            },
        )
        assert expired.status_code == 401
    finally:
        api.app.state.identity_provider = original


def test_demo_identity_provider_validates_self_issued_tokens_only(api):
    from osip_dashboard.identity import encode_demo_token

    secret = "demo-test-secret-1234567890123456789012"
    provider = DemoIdentityProvider(secret=secret)
    actor = Actor(actor_id="demo-risk", roles=frozenset({"reader"}), domains=frozenset({"risk"}), portfolios=frozenset({"*"}))
    token, _ = encode_demo_token(secret=secret, actor=actor, username="risk", display_name="Demo Risk", ttl_minutes=60)

    original = api.app.state.identity_provider
    api.app.state.identity_provider = provider
    try:
        no_token = api.get("/api/v1/portfolios")
        assert no_token.status_code == 401
        assert no_token.headers["WWW-Authenticate"] == "Bearer"

        valid = api.get("/api/v1/risk/overview", headers={"Authorization": f"Bearer {token}"})
        assert valid.status_code == 200

        wrong_domain = api.get(
            "/api/v1/accounting/source-readiness", headers={"Authorization": f"Bearer {token}"}
        )
        assert wrong_domain.status_code == 403

        garbage = api.get("/api/v1/risk/overview", headers={"Authorization": "Bearer not-a-real-token"})
        assert garbage.status_code == 401

        # A token signed with a different secret (e.g. from another demo
        # deployment) must never validate, even though it's structurally a
        # well-formed HS256 JWT.
        other_token, _ = encode_demo_token(
            secret="a-completely-different-secret-value-here",
            actor=actor,
            username="risk",
            display_name="Demo Risk",
            ttl_minutes=60,
        )
        wrong_secret = api.get("/api/v1/risk/overview", headers={"Authorization": f"Bearer {other_token}"})
        assert wrong_secret.status_code == 401

        expired_token, _ = encode_demo_token(secret=secret, actor=actor, username="risk", display_name="Demo Risk", ttl_minutes=-5)
        expired = api.get("/api/v1/risk/overview", headers={"Authorization": f"Bearer {expired_token}"})
        assert expired.status_code == 401
    finally:
        api.app.state.identity_provider = original


def test_oidc_rejects_symmetric_or_unsigned_algorithm_configuration():
    for algorithms in (("HS256",), ("none",), ()):
        try:
            OidcIdentityProvider(
                issuer=ISSUER,
                audience=AUDIENCE,
                jwks_url="https://unused.example/keys",
                role_mapping={"finance-reader": "reader"},
                algorithms=algorithms,
            )
        except ValueError as exc:
            assert "must be asymmetric" in str(exc)
        else:
            raise AssertionError(f"Accepted unsafe algorithms: {algorithms}")
