"""Portfolio, metric-definition, and snapshot catalogue routes."""

from fastapi import APIRouter

from osip_dashboard import api_handlers as handlers
from osip_dashboard.api_schemas import (
    MetricDefinitionList,
    PortfolioListResponse,
    SnapshotListResponse,
)


router = APIRouter(tags=["catalog"])

router.add_api_route(
    "/portfolios",
    handlers.list_portfolios,
    methods=["GET"],
    response_model=PortfolioListResponse,
    summary="List governed portfolios and publication dates",
    operation_id="listPortfolios",
)
router.add_api_route(
    "/metrics",
    handlers.list_metric_definitions,
    methods=["GET"],
    response_model=MetricDefinitionList,
    summary="List governed metric definitions",
    operation_id="listMetricDefinitions",
)
router.add_api_route(
    "/portfolios/{code}/snapshots",
    handlers.list_snapshots,
    methods=["GET"],
    response_model=SnapshotListResponse,
    summary="List portfolio snapshots",
    operation_id="listPortfolioSnapshots",
)
