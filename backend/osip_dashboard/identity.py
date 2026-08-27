"""Identity-provider boundary and development-header implementation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import logging
from typing import Annotated, Any, Protocol

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError, PyJWTError

from osip_dashboard.services.workflow import Actor


BEARER_SCHEME = HTTPBearer(
    auto_error=False,
    scheme_name="OidcBearer",
    description="Production OIDC access token. Development headers are local-only.",
)

ASYMMETRIC_JWT_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)

LOGGER = logging.getLogger("osip_dashboard.identity")


class IdentityProvider(Protocol):
    def actor_from_request(self, request: Request) -> Actor: ...


class DevelopmentHeaderIdentityProvider:
    """Local-only identity supplied through explicit request headers."""

    def actor_from_request(self, request: Request) -> Actor:
        actor_id = request.headers.get("X-Actor-Id", "").strip()
        if not actor_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="В режиме разработки требуется X-Actor-Id",
            )
        roles = frozenset(
            role.strip().lower()
            for role in request.headers.get("X-Actor-Roles", "").split(",")
            if role.strip()
        )
        portfolio_header = request.headers.get("X-Actor-Portfolios")
        portfolios = (
            frozenset(
                code.strip().upper()
                for code in portfolio_header.split(",")
                if code.strip()
            )
            if portfolio_header is not None
            else frozenset({"*"})
        )
        domain_header = request.headers.get("X-Actor-Domains")
        domains = (
            frozenset(
                code.strip().lower()
                for code in domain_header.split(",")
                if code.strip()
            )
            if domain_header is not None
            else frozenset({"*"})
        )
        return Actor(actor_id=actor_id, roles=roles, portfolios=portfolios, domains=domains)


class OidcIdentityProvider:
    """Validate signed bearer JWTs and map external claims explicitly."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        role_mapping: Mapping[str, str],
        actor_id_claim: str = "sub",
        roles_claim: str = "roles",
        portfolios_claim: str = "portfolios",
        domains_claim: str = "domains",
        algorithms: tuple[str, ...] = ("RS256",),
        clock_skew_seconds: int = 60,
        key_resolver: Callable[[str], Any] | None = None,
    ):
        if not algorithms or any(
            algorithm not in ASYMMETRIC_JWT_ALGORITHMS for algorithm in algorithms
        ):
            allowed = ", ".join(sorted(ASYMMETRIC_JWT_ALGORITHMS))
            raise ValueError(
                f"OIDC signing algorithms must be asymmetric and one of: {allowed}"
            )
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.role_mapping = dict(role_mapping)
        self.actor_id_claim = actor_id_claim
        self.roles_claim = roles_claim
        self.portfolios_claim = portfolios_claim
        self.domains_claim = domains_claim
        self.algorithms = algorithms
        self.clock_skew_seconds = clock_skew_seconds
        jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        self.key_resolver = key_resolver or (
            lambda token: jwks_client.get_signing_key_from_jwt(token).key
        )

    def actor_from_request(self, request: Request) -> Actor:
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise _authentication_error("Требуется Bearer-токен")
        try:
            claims = jwt.decode(
                token.strip(),
                self.key_resolver(token.strip()),
                algorithms=list(self.algorithms),
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.clock_skew_seconds,
                options={"require": ["exp", "iat", "iss", "aud", self.actor_id_claim]},
            )
        except (PyJWTError, PyJWKClientError, ValueError, TypeError) as exc:
            raise _authentication_error("Bearer-токен недействителен") from exc

        actor_id = _claim(claims, self.actor_id_claim)
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise _authentication_error("Идентификатор в Bearer-токене недействителен")
        external_roles = _claim_values(_claim(claims, self.roles_claim))
        roles = frozenset(
            self.role_mapping[role]
            for role in external_roles
            if role in self.role_mapping
        )
        portfolios = frozenset(
            code.upper() for code in _claim_values(_claim(claims, self.portfolios_claim))
        )
        domain_claim = _claim(claims, self.domains_claim)
        # Tokens issued before domain scoping was introduced remain valid and
        # retain the legacy all-domain behavior. An explicit empty claim still
        # means no domain access.
        if domain_claim is None:
            LOGGER.warning(
                "OIDC token for actor %r has no %r claim; granting legacy all-domain access",
                actor_id.strip(),
                self.domains_claim,
            )
            domains = frozenset({"*"})
        else:
            domains = frozenset(code.lower() for code in _claim_values(domain_claim))
        return Actor(actor_id=actor_id.strip(), roles=roles, portfolios=portfolios, domains=domains)


DEMO_TOKEN_ALGORITHM = "HS256"


def encode_demo_token(
    *,
    secret: str,
    actor: Actor,
    username: str,
    display_name: str,
    ttl_minutes: int,
) -> tuple[str, datetime]:
    """Issue a self-signed session token for the demo identity provider.

    Symmetric (HS256) signing is appropriate here specifically because the
    app is both the issuer and the sole verifier - unlike OidcIdentityProvider,
    which validates tokens from a third party and therefore must require an
    asymmetric algorithm so it can never itself forge a token it accepts.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)
    claims = {
        "sub": actor.actor_id,
        "username": username,
        "display_name": display_name,
        "roles": sorted(actor.roles),
        "domains": sorted(actor.domains),
        "portfolios": sorted(actor.portfolios),
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(claims, secret, algorithm=DEMO_TOKEN_ALGORITHM)
    return token, expires_at


class DemoIdentityProvider:
    """Validate self-issued demo-login session tokens.

    Unlike OidcIdentityProvider, this trusts no external party: the same
    secret both signs (in the login route) and verifies (here) tokens, so a
    symmetric algorithm is safe. Only tokens this application issued through
    ``POST /api/v1/auth/demo-login`` will ever validate.
    """

    def __init__(self, *, secret: str):
        self.secret = secret

    def actor_from_request(self, request: Request) -> Actor:
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise _authentication_error("Требуется Bearer-токен")
        try:
            claims = jwt.decode(
                token.strip(),
                self.secret,
                algorithms=[DEMO_TOKEN_ALGORITHM],
                options={"require": ["exp", "iat", "sub"]},
            )
        except PyJWTError as exc:
            raise _authentication_error("Токен сессии недействителен") from exc
        actor_id = claims.get("sub")
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise _authentication_error("Токен сессии недействителен")
        return Actor(
            actor_id=actor_id.strip(),
            roles=frozenset(_claim_values(claims.get("roles"))),
            portfolios=frozenset(code.upper() for code in _claim_values(claims.get("portfolios"))),
            domains=frozenset(code.lower() for code in _claim_values(claims.get("domains"))),
        )


def get_actor(
    request: Request,
    _credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(BEARER_SCHEME)
    ],
) -> Actor:
    return request.app.state.identity_provider.actor_from_request(request)


def require_role(actor: Actor, role: str) -> None:
    if role not in actor.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Требуется роль «{role}»",
        )


def require_portfolio(actor: Actor, portfolio_code: str | None) -> None:
    if portfolio_code is None:
        return
    code = portfolio_code.upper()
    if "*" not in actor.portfolios and code not in actor.portfolios:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Нет доступа к портфелю «{code}»",
        )


def require_domain(actor: Actor, domain: str | None) -> None:
    """Enforce a business-domain scope independently of portfolio access."""
    if domain is None or "*" in actor.domains:
        return
    normalized = domain.strip().lower()
    if normalized not in actor.domains:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Нет доступа к области данных «{normalized}»",
        )


def _authentication_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _claim(claims: Mapping[str, Any], path: str) -> Any:
    value: Any = claims
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _claim_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, (list, tuple, set)):
        return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    return ()
