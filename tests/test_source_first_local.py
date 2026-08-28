from pathlib import Path


WORKBOOK_DIR = Path(__file__).resolve().parents[1] / "Portfolio operations"


ACTOR = {
    "X-Actor-Id": "local-back-office",
    "X-Actor-Roles": "uploader,reader,publisher",
    "X-Actor-Domains": "back_office",
    "X-Actor-Portfolios": "SOBSTV",
}


def test_local_source_first_publishes_osip_without_dq_ack(source_first_api):
    workbook = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"))
    response = source_first_api.post(
        "/api/v1/imports",
        files={"file": (workbook.name, workbook.read_bytes(), "application/vnd.ms-excel")},
        data={"portfolio_code": "SOBSTV"},
        headers=ACTOR,
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "published"
    assert payload["publication_basis"] == "trusted_source_local"
    assert payload["publication_requires_override"] is False
    assert payload["dq_counts"]["high"] >= 1

    readiness = source_first_api.get(
        f"/api/v1/snapshots/{payload['snapshot_id']}/report-readiness",
        headers=ACTOR,
    )
    assert readiness.status_code == 200
    readiness_payload = readiness.json()
    assert readiness_payload["gates"]["source_first_mode"] is True
    assert readiness_payload["operational_snapshot_export"]["ready"] is True
    assert readiness_payload["operational_snapshot_export"]["blocking_reasons"] == []

    detail = source_first_api.get(
        f"/api/v1/imports/{payload['id']}", headers=ACTOR
    ).json()
    assert any(
        event["action"] == "import.source_first_published"
        for event in detail["audit_events"]
    )
