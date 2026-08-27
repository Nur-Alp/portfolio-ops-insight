from datetime import timedelta

from osip_dashboard.persistence.models import DemoAccount, utcnow
from osip_dashboard.services.demo_auth import AccountLocked, authenticate, hash_password, verify_password


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_verify_password_rejects_malformed_stored_hash():
    assert not verify_password("anything", "not-a-scrypt-hash")


def test_authenticate_returns_none_for_wrong_password_and_resets_on_success(demo_api):
    engine = demo_api.app.state.engine
    from osip_dashboard.persistence.database import create_session_factory

    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(
            DemoAccount(
                username="tester",
                password_hash=hash_password("right-password"),
                display_name="Tester",
                actor_id="demo-tester",
                roles="reader",
                domains="risk",
                portfolios="*",
            )
        )
        session.commit()

        assert authenticate(session, "tester", "wrong", max_failed_attempts=8, lockout_minutes=15) is None
        account = session.query(DemoAccount).filter_by(username="tester").one()
        assert account.failed_attempts == 1

        result = authenticate(session, "tester", "right-password", max_failed_attempts=8, lockout_minutes=15)
        assert result is not None
        assert result.failed_attempts == 0


def test_authenticate_locks_out_after_max_failed_attempts(demo_api):
    engine = demo_api.app.state.engine
    from osip_dashboard.persistence.database import create_session_factory

    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(
            DemoAccount(
                username="lockout-test",
                password_hash=hash_password("right-password"),
                display_name="Lockout Test",
                actor_id="demo-lockout",
                roles="reader",
                domains="risk",
                portfolios="*",
            )
        )
        session.commit()

        for _ in range(3):
            assert authenticate(session, "lockout-test", "wrong", max_failed_attempts=3, lockout_minutes=15) is None

        try:
            authenticate(session, "lockout-test", "right-password", max_failed_attempts=3, lockout_minutes=15)
            assert False, "expected AccountLocked"
        except AccountLocked:
            pass


def test_authenticate_rejects_disabled_accounts(demo_api):
    engine = demo_api.app.state.engine
    from osip_dashboard.persistence.database import create_session_factory

    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(
            DemoAccount(
                username="disabled-user",
                password_hash=hash_password("right-password"),
                display_name="Disabled",
                actor_id="demo-disabled",
                roles="reader",
                domains="risk",
                portfolios="*",
                disabled=True,
            )
        )
        session.commit()
        assert authenticate(session, "disabled-user", "right-password", max_failed_attempts=8, lockout_minutes=15) is None


def test_authenticate_unlocks_after_lockout_window_passes(demo_api):
    engine = demo_api.app.state.engine
    from osip_dashboard.persistence.database import create_session_factory

    session_factory = create_session_factory(engine)
    with session_factory() as session:
        account = DemoAccount(
            username="expired-lock",
            password_hash=hash_password("right-password"),
            display_name="Expired Lock",
            actor_id="demo-expired-lock",
            roles="reader",
            domains="risk",
            portfolios="*",
            locked_until=utcnow() - timedelta(minutes=1),
        )
        session.add(account)
        session.commit()

        result = authenticate(session, "expired-lock", "right-password", max_failed_attempts=8, lockout_minutes=15)
        assert result is not None
