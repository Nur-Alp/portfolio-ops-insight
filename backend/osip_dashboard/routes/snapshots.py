"""Published snapshot read-model routes."""

from fastapi import APIRouter

from osip_dashboard import api_handlers as handlers
from osip_dashboard.api_schemas import (
    AllocationResponse,
    CalendarResponse,
    CashResponse,
    DqAssignmentResponse,
    HoldingsResponse,
    IssuesResponse,
    ReportReadinessResponse,
    SettlementsResponse,
    SnapshotOverview,
    SnapshotProvenanceResponse,
)


router = APIRouter(tags=["snapshots"])

router.add_api_route(
    "/snapshots/{snapshot_id}/overview",
    handlers.snapshot_overview,
    methods=["GET"],
    response_model=SnapshotOverview,
    summary="Read snapshot totals with metric bases",
    operation_id="getSnapshotOverview",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/provenance",
    handlers.snapshot_provenance,
    methods=["GET"],
    response_model=SnapshotProvenanceResponse,
    summary="Read exact source and derivation lineage for snapshot metrics",
    operation_id="getSnapshotProvenance",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/holdings",
    handlers.snapshot_holdings,
    methods=["GET"],
    response_model=HoldingsResponse,
    summary="Read immutable lots or the instrument aggregation",
    operation_id="getSnapshotHoldings",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/holdings/export",
    handlers.export_snapshot_holdings,
    methods=["GET"],
    response_model=None,
    response_class=handlers.XlsxResponse,
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
            "description": "Excel workbook with the filtered instrument view",
        }
    },
    summary="Export the filtered instrument view as an Excel workbook",
    operation_id="exportSnapshotHoldings",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/lots/export",
    handlers.export_snapshot_lots,
    methods=["GET"],
    response_model=None,
    response_class=handlers.XlsxResponse,
    responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"schema": {"type": "string", "format": "binary"}}}, "description": "Excel workbook with immutable source lots"}},
    summary="Export immutable source lots as an Excel workbook",
    operation_id="exportSnapshotLots",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/allocations",
    handlers.snapshot_allocations,
    methods=["GET"],
    response_model=AllocationResponse,
    summary="Read basis-aware portfolio allocation",
    operation_id="getSnapshotAllocations",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/cash",
    handlers.snapshot_cash,
    methods=["GET"],
    response_model=CashResponse,
    summary="Read cash balances and source evidence",
    operation_id="getSnapshotCash",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/cash-calendar/export",
    handlers.export_snapshot_cash_calendar,
    methods=["GET"],
    response_model=None,
    response_class=handlers.XlsxResponse,
    responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"schema": {"type": "string", "format": "binary"}}}, "description": "Excel workbook with cash and operational calendar"}},
    summary="Export cash and operational calendar as an Excel workbook",
    operation_id="exportSnapshotCashCalendar",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/settlements",
    handlers.snapshot_settlements,
    methods=["GET"],
    response_model=SettlementsResponse,
    summary="Read raw-lineage-preserving settlements",
    operation_id="getSnapshotSettlements",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/issues",
    handlers.snapshot_issues,
    methods=["GET"],
    response_model=IssuesResponse,
    summary="Read data-quality findings and acknowledgements",
    operation_id="getSnapshotIssues",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/issues/export",
    handlers.export_snapshot_issues,
    methods=["GET"],
    response_model=None,
    response_class=handlers.XlsxResponse,
    responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"schema": {"type": "string", "format": "binary"}}}, "description": "Excel workbook with filtered data-quality findings"}},
    summary="Export filtered data-quality findings as an Excel workbook",
    operation_id="exportSnapshotIssues",
)
router.add_api_route(
    "/issues/{issue_id}/assign",
    handlers.assign_dq_issue,
    methods=["POST"],
    response_model=DqAssignmentResponse,
    summary="Assign or clear a data-quality finding's owner and due date",
    operation_id="assignDqIssue",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/calendar",
    handlers.snapshot_calendar,
    methods=["GET"],
    response_model=CalendarResponse,
    summary="Read operational dated events",
    operation_id="getSnapshotCalendar",
)
router.add_api_route(
    "/snapshots/{snapshot_id}/report-readiness",
    handlers.snapshot_report_readiness,
    methods=["GET"],
    response_model=ReportReadinessResponse,
    summary="Read controlled export gates",
    operation_id="getSnapshotReportReadiness",
)
