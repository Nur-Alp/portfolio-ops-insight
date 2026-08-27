"""Seed the fixed demo-persona login accounts (and the sanitized synthetic
dataset they read) for a shareable demo deployment running the ``demo``
identity provider.

Safe to re-run: both the account seed and the dataset seed are idempotent.
Never touches ``.data/local-dashboard`` (the real local dev data) - this
targets whatever ``OSIP_DATABASE_URL`` points at, which for a demo
deployment must be a separate database from the real one.

Usage:
    OSIP_DATABASE_URL=... OSIP_BLOB_ROOT=... \\
        .venv/bin/python scripts/seed_demo_accounts.py

Per-persona passwords can be supplied via ``OSIP_DEMO_PASSWORD_<USERNAME>``
(username upper-cased, hyphens to underscores, e.g. ``OSIP_DEMO_PASSWORD_ACCOUNTING``).
Any persona left unset gets a random password, printed once below - save it,
it is not recoverable afterwards (only its hash is stored) - except
``supervisor``, whose password is always ``0000`` (see ``_FIXED_PASSWORDS``
below): a deliberate, permanent exception, re-applied on every run.
"""

from __future__ import annotations

import os

from sqlalchemy import select

from osip_dashboard.config import get_settings
from osip_dashboard.persistence.database import create_database_engine, create_session_factory
from osip_dashboard.persistence.models import DemoAccount, utcnow
from osip_dashboard.services.demo_accounts_seed import DemoAccountSpec, seed_demo_accounts
from osip_dashboard.services.demo_multi_source import seed_multi_source_demo
from osip_dashboard.storage import LocalBlobStore


# actor_id "e2e-uploader" matches the uploader_id every seed_multi_source_demo
# record is created under - a persona's actor_id must match it or the
# per-uploader visibility rule (docs/domain-upload-instructions.md) hides
# the seeded data even though the persona's domain claim is correct.
_SEEDED_DATA_UPLOADER = "e2e-uploader"

# One domain, one person: unlike a demo where many strangers might share a
# single domain login (which is why risk/risk-uploader used to be split -
# a read-only persona plus a separate-identity uploader, so one visitor's
# test upload could never appear as everyone else's data), each domain here
# has exactly one owner. That owner is trusted with both viewing and
# uploading for their own domain, so every domain persona gets the full
# workflow instead of being split into a read-only + upload-only pair.
_DOMAIN_ROLES = "uploader,reviewer,publisher,reader"

PERSONAS: list[DemoAccountSpec] = [
    DemoAccountSpec("risk", "Демо: Риски", _SEEDED_DATA_UPLOADER, _DOMAIN_ROLES, "risk"),
    DemoAccountSpec("accounting", "Демо: Бухгалтерия", _SEEDED_DATA_UPLOADER, _DOMAIN_ROLES, "accounting"),
    DemoAccountSpec("back-office", "Демо: Бэк-офис", _SEEDED_DATA_UPLOADER, _DOMAIN_ROLES, "back_office"),
    DemoAccountSpec("client-ops", "Демо: Клиентские операции", _SEEDED_DATA_UPLOADER, _DOMAIN_ROLES, "client_ops"),
    DemoAccountSpec("corpfin", "Демо: Корпоративные финансы", _SEEDED_DATA_UPLOADER, _DOMAIN_ROLES, "corpfin"),
    # supervisor stays read-only: an all-domains observer, not a domain
    # owner, so the "one person, one domain" trust argument above doesn't
    # apply to it. supervisor2 is a second such observer - sharing the same
    # actor_id is fine here (unlike domain owners) since two read-only
    # logins looking at the same all-domains view have no upload-attribution
    # conflict to keep separate.
    DemoAccountSpec("supervisor", "Демо: Наблюдатель (все домены)", _SEEDED_DATA_UPLOADER, "reader", "*"),
    DemoAccountSpec("supervisor2", "Демо: Наблюдатель (все домены) 2", _SEEDED_DATA_UPLOADER, "reader", "*"),
]

# Personas removed from PERSONAS above (risk-uploader, folded into risk)
# but which may still have a login row from a previous seed run - disabled
# rather than deleted, so the account/audit history isn't destroyed.
_RETIRED_USERNAMES = ["risk-uploader"]


# supervisor is read-only and all-domains-visible with nothing sensitive
# behind it - fixed rather than generated so it's always known without
# having to read the once-only printed output. Re-applied every run
# (unlike every other persona, whose password is left alone once set) so
# it can never drift from this value.
_FIXED_PASSWORDS: dict[str, str] = {"supervisor": "0000"}


def _env_password_key(username: str) -> str:
    return "OSIP_DEMO_PASSWORD_" + username.upper().replace("-", "_")


def main() -> None:
    settings = get_settings()
    if settings.identity_provider != "demo":
        raise SystemExit(
            "OSIP_IDENTITY_PROVIDER must be 'demo' to seed demo accounts "
            f"(currently '{settings.identity_provider}')"
        )
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    blob_store = LocalBlobStore(settings.blob_root)

    password_overrides = {
        **_FIXED_PASSWORDS,
        **{
            persona.username: value
            for persona in PERSONAS
            if (value := os.environ.get(_env_password_key(persona.username)))
        },
    }

    with session_factory() as session:
        seed_multi_source_demo(session, blob_store)
        results = seed_demo_accounts(session, PERSONAS, password_overrides=password_overrides)
        retired = 0
        for username in _RETIRED_USERNAMES:
            account = session.scalar(select(DemoAccount).where(DemoAccount.username == username))
            if account is not None and not account.disabled:
                account.disabled = True
                account.updated_at = utcnow()
                retired += 1
        session.commit()

    if retired:
        print(f"Disabled {retired} retired persona login(s): {', '.join(_RETIRED_USERNAMES)}\n")

    print(f"Seeded {len(results)} demo account(s):")
    shown: dict[str, str] = {}
    for result in results:
        state = "created" if result.created else "updated"
        print(f"  - {result.username}: {state}")
        if result.plaintext_password is not None:
            shown[result.username] = result.plaintext_password

    if shown:
        print(
            "\nPasswords set just now - shown once, only their hash is "
            "stored. Save these now:\n"
        )
        for username, password in shown.items():
            print(f"  {username}: {password}")


if __name__ == "__main__":
    main()
