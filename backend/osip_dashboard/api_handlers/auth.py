"""Demo-persona login HTTP handler."""

from __future__ import annotations

from fastapi import HTTPException, Request

from osip_dashboard.api_schemas import DemoLoginRequest, DemoLoginResponse
from osip_dashboard.identity import encode_demo_token
from osip_dashboard.services.demo_auth import AccountLocked, authenticate as authenticate_demo_account
from osip_dashboard.services.workflow import Actor

from .shared import SessionDep


def demo_login(session: SessionDep, request: Request, body: DemoLoginRequest) -> DemoLoginResponse:
    """Exchange demo-persona credentials for a short-lived session token.

    Only meaningful when the app is running with the ``demo`` identity
    provider; returns 404 otherwise so a non-demo deployment doesn't expose
    a login form that can never actually authenticate anything.
    """
    settings = request.app.state.settings
    if settings.identity_provider != "demo" or not settings.demo_jwt_secret:
        raise HTTPException(status_code=404, detail="Демо-вход не включён")
    try:
        account = authenticate_demo_account(
            session,
            body.username,
            body.password,
            max_failed_attempts=settings.demo_max_failed_attempts,
            lockout_minutes=settings.demo_lockout_minutes,
        )
    except AccountLocked as exc:
        raise HTTPException(
            status_code=401,
            detail="Учётная запись временно заблокирована из-за неудачных попыток входа. Повторите попытку позже.",
        ) from exc
    if account is None:
        raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль")
    actor = Actor(
        actor_id=account.actor_id,
        roles=frozenset(role.strip() for role in account.roles.split(",") if role.strip()),
        domains=frozenset(code.strip().lower() for code in account.domains.split(",") if code.strip()),
        portfolios=frozenset(code.strip().upper() for code in account.portfolios.split(",") if code.strip()),
    )
    token, expires_at = encode_demo_token(
        secret=settings.demo_jwt_secret,
        actor=actor,
        username=account.username,
        display_name=account.display_name,
        ttl_minutes=settings.demo_token_ttl_minutes,
    )
    return DemoLoginResponse(
        access_token=token,
        expires_at=expires_at.isoformat(),
        actor={
            "actor_id": actor.actor_id,
            "username": account.username,
            "display_name": account.display_name,
            "roles": sorted(actor.roles),
            "domains": sorted(actor.domains),
            "portfolios": sorted(actor.portfolios),
        },
    )
