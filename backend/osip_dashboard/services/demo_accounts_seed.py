"""Idempotent seeding for the fixed demo-persona login accounts.

Mirrors the idempotency shape already used by ``seed_multi_source_demo``:
safe to call on every startup, upserts by username, and only ever mutates a
password when the caller explicitly supplies a new one (so re-running the
seed script doesn't silently rotate credentials someone is already using).
"""

from __future__ import annotations

from dataclasses import dataclass
import secrets
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from osip_dashboard.persistence.models import DemoAccount, utcnow
from osip_dashboard.services.demo_auth import hash_password


_PASSWORD_ALPHABET = string.ascii_letters + string.digits
_PASSWORD_LENGTH = 6


def _generate_password() -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH))


@dataclass(frozen=True)
class DemoAccountSpec:
    username: str
    display_name: str
    actor_id: str
    roles: str
    domains: str
    portfolios: str = "*"


@dataclass(frozen=True)
class SeededAccountResult:
    username: str
    created: bool
    # Only set when this call chose the password - either an explicit
    # override was supplied, or the account was brand new and needed one
    # generated. ``None`` means an existing account's password was left
    # untouched (re-running the seed script must never silently rotate a
    # credential someone might already be using).
    plaintext_password: str | None


def seed_demo_accounts(
    session: Session,
    specs: list[DemoAccountSpec],
    *,
    password_overrides: dict[str, str] | None = None,
) -> list[SeededAccountResult]:
    """Create or refresh each persona.

    ``password_overrides`` maps username -> a plaintext password to force-set
    even for an existing account. Any persona not in that mapping keeps its
    existing password hash untouched - unless it doesn't have an account yet,
    in which case one is generated here (and returned in the result, since
    the caller has to show it to someone exactly once).
    """
    password_overrides = password_overrides or {}
    results: list[SeededAccountResult] = []
    for spec in specs:
        account = session.scalar(select(DemoAccount).where(DemoAccount.username == spec.username))
        created = account is None
        plaintext_password: str | None = None
        if account is None:
            plaintext_password = password_overrides.get(spec.username) or _generate_password()
            account = DemoAccount(
                username=spec.username,
                password_hash=hash_password(plaintext_password),
                display_name=spec.display_name,
                actor_id=spec.actor_id,
                roles=spec.roles,
                domains=spec.domains,
                portfolios=spec.portfolios,
            )
            session.add(account)
        else:
            account.display_name = spec.display_name
            account.actor_id = spec.actor_id
            account.roles = spec.roles
            account.domains = spec.domains
            account.portfolios = spec.portfolios
            if spec.username in password_overrides:
                plaintext_password = password_overrides[spec.username]
                account.password_hash = hash_password(plaintext_password)
                account.failed_attempts = 0
                account.locked_until = None
        account.updated_at = utcnow()
        results.append(
            SeededAccountResult(username=spec.username, created=created, plaintext_password=plaintext_password)
        )
    session.flush()
    return results
