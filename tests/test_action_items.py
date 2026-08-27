"""Tests for the action-item CRUD/workflow API."""

from __future__ import annotations


REVIEWER = {"X-Actor-Id": "reviewer", "X-Actor-Roles": "reviewer,reader", "X-Actor-Domains": "risk"}
READER = {"X-Actor-Id": "reader", "X-Actor-Roles": "reader", "X-Actor-Domains": "risk"}
OTHER_DOMAIN_REVIEWER = {"X-Actor-Id": "reviewer2", "X-Actor-Roles": "reviewer,reader", "X-Actor-Domains": "accounting"}


def _create(api, **overrides):
    body = {
        "domain": "risk",
        "kind": "breach_exception",
        "title": "Follow up on SOBSTV country-limit breach",
        "reference_key": "risk_limits_sobstv:country:Россия",
    }
    body.update(overrides)
    return api.post("/api/v1/action-items", headers=REVIEWER, json=body)


def test_create_and_get_action_item(api):
    created = _create(api)
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["status"] == "open"
    assert payload["domain"] == "risk"
    assert payload["created_by"] == "reviewer"
    assert payload["owner_id"] is None
    assert payload["is_overdue"] is False

    fetched = api.get(f"/api/v1/action-items/{payload['id']}", headers=READER)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == payload["id"]


def test_create_rejects_cross_domain_actor(api):
    denied = api.post(
        "/api/v1/action-items",
        headers=OTHER_DOMAIN_REVIEWER,
        json={"domain": "risk", "kind": "breach_exception", "title": "x"},
    )
    assert denied.status_code == 403


def test_list_filters_by_domain_status_kind(api):
    _create(api)
    _create(api, kind="close_step", title="Close accounting period", domain="accounting")
    listed = api.get("/api/v1/action-items", headers={**REVIEWER, "X-Actor-Domains": "*"}, params={"domain": "risk"})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["domain"] == "risk"


def test_assign_requires_reason_and_persists_owner(api):
    created = _create(api).json()
    item_id = created["id"]

    missing_reason = api.post(
        f"/api/v1/action-items/{item_id}/assign",
        headers=REVIEWER,
        json={"owner_id": "risk-officer", "due_date": None, "reason": ""},
    )
    assert missing_reason.status_code == 422, missing_reason.text

    assigned = api.post(
        f"/api/v1/action-items/{item_id}/assign",
        headers=REVIEWER,
        json={"owner_id": "risk-officer", "due_date": "2026-08-15", "reason": "Owner confirmed by risk committee"},
    )
    assert assigned.status_code == 200, assigned.text
    payload = assigned.json()
    assert payload["owner_id"] == "risk-officer"
    assert payload["due_date"] == "2026-08-15"
    assert payload["assigned_by"] == "reviewer"
    assert payload["assignment_reason"] == "Owner confirmed by risk committee"


def test_resolve_then_reopen_round_trip(api):
    created = _create(api).json()
    item_id = created["id"]

    resolved = api.post(
        f"/api/v1/action-items/{item_id}/resolve",
        headers=REVIEWER,
        json={"comment": "Breach cleared after month-end rebalance"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_by"] == "reviewer"

    cannot_assign_resolved = api.post(
        f"/api/v1/action-items/{item_id}/assign",
        headers=REVIEWER,
        json={"owner_id": "someone", "due_date": None, "reason": "trying anyway"},
    )
    assert cannot_assign_resolved.status_code == 409

    reopened = api.post(
        f"/api/v1/action-items/{item_id}/reopen",
        headers=REVIEWER,
        json={"reason": "Breach recurred in the following period"},
    )
    assert reopened.status_code == 200, reopened.text
    payload = reopened.json()
    assert payload["status"] == "open"
    assert payload["resolved_by"] is None
    assert payload["resolved_at"] is None


def test_overdue_flag_reflects_due_date(api):
    created = _create(api).json()
    item_id = created["id"]
    api.post(
        f"/api/v1/action-items/{item_id}/assign",
        headers=REVIEWER,
        json={"owner_id": "risk-officer", "due_date": "2020-01-01", "reason": "Backdated for test"},
    )
    fetched = api.get(f"/api/v1/action-items/{item_id}", headers=READER)
    assert fetched.json()["is_overdue"] is True


def test_get_missing_item_is_404(api):
    missing = api.get("/api/v1/action-items/00000000-0000-0000-0000-000000000000", headers=READER)
    assert missing.status_code == 404
