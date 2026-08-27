"""Snapshot CSV report HTTP handlers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from osip_dashboard.api_schemas import ExportRequest
from osip_dashboard.identity import require_domain, require_portfolio, require_role
from osip_dashboard.persistence.models import ReportRun
from osip_dashboard.services.reporting import generate_csv_report

from .shared import ActorDep, SessionDep, _get_snapshot, _iso, router


@router.get("/snapshots/{snapshot_id}/reports")
def list_snapshot_reports(snapshot_id: UUID, session: SessionDep, actor: ActorDep) -> dict[str, Any]:
    require_role(actor, "reader")
    _get_snapshot(session, snapshot_id, actor)
    reports = list(session.scalars(select(ReportRun).where(ReportRun.snapshot_id == snapshot_id).order_by(ReportRun.created_at.desc())))
    return {"items": [_report_payload(report) for report in reports]}


@router.post("/snapshots/{snapshot_id}/reports", status_code=201)
def create_snapshot_report(snapshot_id: UUID, body: ExportRequest, session: SessionDep, actor: ActorDep, request: Request) -> dict[str, Any]:
    require_role(actor, "publisher")
    require_domain(actor, "back_office")
    try:
        report = generate_csv_report(
            session,
            request.app.state.blob_store,
            _get_snapshot(session, snapshot_id, actor),
            actor.actor_id,
            allow_unacknowledged_dq=request.app.state.settings.source_first_mode,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _report_payload(report)


@router.get("/reports/{report_id}/artifact")
def get_report_artifact(report_id: UUID, session: SessionDep, actor: ActorDep, request: Request) -> FileResponse:
    require_role(actor, "reader")
    require_domain(actor, "back_office")
    report = session.get(ReportRun, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Артефакт отчёта не найден")
    require_portfolio(actor, report.snapshot.portfolio_code)
    return FileResponse(
        request.app.state.blob_store.path_for(report.storage_key),
        filename=f"OSIP-{report.snapshot.portfolio_code}-{report.snapshot.report_date}-v{report.snapshot.version}.csv",
        media_type="text/csv; charset=utf-8",
    )


def _report_payload(report: ReportRun) -> dict[str, Any]:
    return {
        "id": str(report.id),
        "snapshot_id": str(report.snapshot_id),
        "format": report.format,
        "requested_by": report.requested_by,
        "artifact_sha256": report.artifact_sha256,
        "disclosures": report.disclosures,
        "created_at": _iso(report.created_at),
        "artifact_url": f"/api/v1/reports/{report.id}/artifact",
    }
