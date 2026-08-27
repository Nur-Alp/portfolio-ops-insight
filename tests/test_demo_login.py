from osip_dashboard.persistence.database import create_session_factory
from osip_dashboard.persistence.models import DemoAccount
from osip_dashboard.services.demo_auth import hash_password


def _seed_account(demo_api, **overrides):
    session_factory = create_session_factory(demo_api.app.state.engine)
    defaults = dict(
        username="risk",
        password_hash=hash_password("hunter2pass"),
        display_name="Демо: Риски",
        actor_id="demo-risk",
        roles="reader",
        domains="risk",
        portfolios="*",
    )
    defaults.update(overrides)
    with session_factory() as session:
        session.add(DemoAccount(**defaults))
        session.commit()


def test_wrong_password_is_rejected_generically(demo_api):
    _seed_account(demo_api)
    response = demo_api.post("/api/v1/auth/demo-login", json={"username": "risk", "password": "wrong"})
    assert response.status_code == 401
    assert "заблокирован" not in response.json()["detail"]


def test_unknown_username_gets_the_same_generic_message_as_wrong_password(demo_api):
    _seed_account(demo_api)
    wrong_password = demo_api.post("/api/v1/auth/demo-login", json={"username": "risk", "password": "wrong"})
    unknown_user = demo_api.post("/api/v1/auth/demo-login", json={"username": "nobody", "password": "wrong"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["detail"] == unknown_user.json()["detail"]


def test_successful_login_issues_a_token_that_authorizes_only_its_own_domain(demo_api):
    _seed_account(demo_api)
    response = demo_api.post("/api/v1/auth/demo-login", json={"username": "risk", "password": "hunter2pass"})
    assert response.status_code == 200
    body = response.json()
    assert body["actor"]["domains"] == ["risk"]
    token = body["access_token"]

    allowed = demo_api.get("/api/v1/risk/overview", headers={"Authorization": f"Bearer {token}"})
    assert allowed.status_code == 200

    denied = demo_api.get("/api/v1/accounting/source-readiness", headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == 403


def test_lockout_after_repeated_failures_reports_a_distinct_message(demo_api):
    _seed_account(demo_api)
    for _ in range(3):
        response = demo_api.post("/api/v1/auth/demo-login", json={"username": "risk", "password": "wrong"})
        assert response.status_code == 401

    locked_out = demo_api.post("/api/v1/auth/demo-login", json={"username": "risk", "password": "hunter2pass"})
    assert locked_out.status_code == 401
    assert "заблокирован" in locked_out.json()["detail"]


def test_disabled_account_cannot_log_in(demo_api):
    _seed_account(demo_api, disabled=True)
    response = demo_api.post("/api/v1/auth/demo-login", json={"username": "risk", "password": "hunter2pass"})
    assert response.status_code == 401


def test_demo_login_route_is_404_when_identity_provider_is_not_demo(api):
    response = api.post("/api/v1/auth/demo-login", json={"username": "risk", "password": "whatever"})
    assert response.status_code == 404
