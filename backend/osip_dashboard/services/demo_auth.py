"""Password hashing and login verification for the demo identity provider.

Uses stdlib ``hashlib.scrypt`` rather than adding a new dependency (bcrypt/
argon2) - scrypt is a standard password-hashing KDF and is already available
in every supported Python version. This is deliberately scoped to a small,
fixed set of demo personas, not a general user-account system.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from osip_dashboard.persistence.models import DemoAccount, utcnow


def _as_aware_utc(value: datetime) -> datetime:
    # SQLite does not actually persist tzinfo: a DateTime(timezone=True)
    # column round-trips as a naive datetime even though it was written
    # with one, and every value this app writes to it is UTC - so a naive
    # read-back is always safe to reattach UTC to before comparing.
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_LENGTH = 32


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_LENGTH
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(hash_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived.hex(), hash_hex)


class AccountLocked(Exception):
    """Too many recent failed attempts; the account is temporarily locked."""


def authenticate(
    session: Session,
    username: str,
    password: str,
    *,
    max_failed_attempts: int,
    lockout_minutes: int,
) -> DemoAccount | None:
    """Verify credentials, applying lockout after repeated failures.

    Returns the account on success, ``None`` on a wrong username/password
    (deliberately indistinguishable from each other to avoid username
    enumeration), and raises ``AccountLocked`` when locked out - that case
    is reported distinctly to the caller so a locked-out legitimate user
    gets a clearer message than "wrong password".
    """
    account = session.scalar(
        select(DemoAccount).where(func.lower(DemoAccount.username) == username.strip().lower())
    )
    if account is None or account.disabled:
        return None
    now = utcnow()
    if account.locked_until is not None and _as_aware_utc(account.locked_until) > now:
        raise AccountLocked()
    if not verify_password(password, account.password_hash):
        account.failed_attempts += 1
        if account.failed_attempts >= max_failed_attempts:
            account.locked_until = now + timedelta(minutes=lockout_minutes)
            account.failed_attempts = 0
        account.updated_at = now
        session.commit()
        return None
    account.failed_attempts = 0
    account.locked_until = None
    account.updated_at = now
    session.commit()
    return account
