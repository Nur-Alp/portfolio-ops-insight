"""Versioned OSIP API assembled from domain route modules."""

from fastapi import APIRouter

from osip_dashboard.routes import (
    action_items_router,
    auth_router,
    catalog_router,
    imports_router,
    reports_router,
    snapshots_router,
    multi_source_router,
)


router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(imports_router)
router.include_router(catalog_router)
router.include_router(snapshots_router)
router.include_router(reports_router)
router.include_router(multi_source_router)
router.include_router(action_items_router)
