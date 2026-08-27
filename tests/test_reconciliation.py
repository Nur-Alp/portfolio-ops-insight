from decimal import Decimal

from osip_dashboard.operations.reconciliation import (
    collect_recovery_state,
    compare_recovery_states,
)


UPLOADER = {"X-Actor-Id": "recovery-uploader", "X-Actor-Roles": "uploader,reader"}
REVIEWER = {"X-Actor-Id": "recovery-reviewer", "X-Actor-Roles": "reviewer,reader"}
PUBLISHER = {"X-Actor-Id": "recovery-publisher", "X-Actor-Roles": "publisher,reader"}


def test_recovery_state_reconciles_database_business_values_and_blob_hashes(
    api, workbook_paths
):
    path = workbook_paths["SOBSTV"]
    imported = api.post(
        "/api/v1/imports",
        files={"file": (path.name, path.read_bytes(), "application/vnd.ms-excel")},
        data={"portfolio_code": "SOBSTV"},
        headers=UPLOADER,
    ).json()
    issues = api.get(
        f"/api/v1/snapshots/{imported['snapshot_id']}/issues", headers=UPLOADER
    ).json()["items"]
    codes = sorted(
        {issue["code"] for issue in issues if issue["severity"] in {"blocker", "high"}}
    )
    referenced_issues = [issue for issue in issues if issue["source_refs"]]
    assert referenced_issues
    assert all(
        ref["source_row_id"]
        for issue in referenced_issues
        for ref in issue["source_refs"]
    )
    api.post(
        f"/api/v1/imports/{imported['id']}/approve",
        json={"comment": "Recovery fixture review", "acknowledged_dq_codes": codes},
        headers=REVIEWER,
    )
    api.post(f"/api/v1/imports/{imported['id']}/publish", headers=PUBLISHER)
    report = api.post(
        f"/api/v1/snapshots/{imported['snapshot_id']}/reports",
        json={},
        headers=PUBLISHER,
    )
    assert report.status_code == 201

    with api.app.state.session_factory() as session:
        state = collect_recovery_state(session, api.app.state.blob_store)

    assert state["integrity_errors"] == []
    assert state["counts"]["imports"] == 1
    assert state["counts"]["snapshots"] == 1
    assert state["counts"]["position_lots"] == 19
    assert state["counts"]["report_runs"] == 1
    assert state["source_files"][0]["actual_sha256"] == imported["source_sha256"]
    assert Decimal(
        state["snapshots"][0]["derived_operational_total_kzt"]
    ).quantize(Decimal("0.01")) == Decimal("4816373033.99")
    assert compare_recovery_states(state, state) == []

    changed = {**state, "counts": {**state["counts"], "position_lots": 18}}
    assert compare_recovery_states(state, changed) == [
        "counts differs from the pre-backup baseline"
    ]
