"""One-off: add the 'admin' role to the seeded 'admin' demo account so it
can use the cross-uploader visibility bypass added in _actor_can_read_uploader_id
(backend/osip_dashboard/routes/multi_source.py). Password is left untouched.
"""

from __future__ import annotations

from osip_dashboard.persistence.database import create_database_engine, create_session_factory
from osip_dashboard.services.demo_accounts_seed import DemoAccountSpec, seed_demo_accounts

DATABASE_URL = "sqlite:///.data/local-dashboard/runtime/dashboard.sqlite3"


def main() -> None:
    engine = create_database_engine(DATABASE_URL)
    session_factory = create_session_factory(engine)
    spec = DemoAccountSpec(
        username="admin",
        display_name="Admin (all domains)",
        actor_id="local-operator",
        roles="admin,uploader,reviewer,publisher,reader",
        domains="*",
        portfolios="*",
    )
    with session_factory() as session:
        results = seed_demo_accounts(session, [spec])
        session.commit()
    for result in results:
        print(f"{result.username}: created={result.created}, password left untouched={result.plaintext_password is None}")


if __name__ == "__main__":
    main()
