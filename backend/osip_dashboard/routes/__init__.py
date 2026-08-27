"""Domain routers for the versioned API."""

from osip_dashboard.routes.action_items import router as action_items_router
from osip_dashboard.routes.auth import router as auth_router
from osip_dashboard.routes.catalog import router as catalog_router
from osip_dashboard.routes.imports import router as imports_router
from osip_dashboard.routes.reports import router as reports_router
from osip_dashboard.routes.snapshots import router as snapshots_router
from osip_dashboard.routes.multi_source import router as multi_source_router

__all__ = [
    "action_items_router",
    "auth_router",
    "catalog_router",
    "imports_router",
    "reports_router",
    "snapshots_router",
    "multi_source_router",
]
