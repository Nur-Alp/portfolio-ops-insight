"""Controlled report generation and artifact routes."""

from fastapi import APIRouter

from osip_dashboard import api_handlers as handlers
from osip_dashboard.api_schemas import ReportArtifact, ReportListResponse


router = APIRouter(tags=["reports"])

router.add_api_route(
    "/snapshots/{snapshot_id}/reports",
    handlers.list_snapshot_reports,
    methods=["GET"],
    response_model=ReportListResponse,
    summary="List immutable report runs",
    operation_id="listSnapshotReports",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/reports",
    handlers.create_snapshot_report,
    methods=["POST"],
    response_model=ReportArtifact,
    status_code=201,
    summary="Generate a controlled operational export",
    operation_id="createSnapshotReport",
)
router.add_api_route(
    "/reports/{report_id}/artifact",
    handlers.get_report_artifact,
    methods=["GET"],
    response_model=None,
    summary="Download an exact report artifact",
    operation_id="downloadReportArtifact",
)
