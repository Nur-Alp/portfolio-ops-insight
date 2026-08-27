"""Immutable workbook import and review workflow routes."""

from fastapi import APIRouter

from osip_dashboard import api_handlers as handlers
from osip_dashboard.api_schemas import (
    ImportComparisonResponse,
    ImportDetail,
    ImportListResponse,
    ImportRecord,
    ReferenceDictionaryStatus,
    ReferenceDictionaryUploadResponse,
    DividendDataStatus,
    DividendDataUploadResponse,
    SourcePreviewResponse,
)


router = APIRouter(tags=["imports"])

router.add_api_route(
    "/imports",
    handlers.create_import,
    methods=["POST"],
    response_model=ImportRecord,
    status_code=201,
    summary="Import an immutable OSIP workbook",
    operation_id="createImport",
    responses={200: {"model": ImportRecord, "description": "Identical source already exists"}},
)
router.add_api_route(
    "/imports",
    handlers.list_imports,
    methods=["GET"],
    response_model=ImportListResponse,
    summary="List workbook imports",
    operation_id="listImports",
)
router.add_api_route(
    "/imports/export",
    handlers.export_import_registry,
    methods=["GET"],
    response_model=None,
    response_class=handlers.XlsxResponse,
    responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"schema": {"type": "string", "format": "binary"}}}, "description": "Excel workbook with the visible import registry and audit"}},
    summary="Export visible import registry and audit as an Excel workbook",
    operation_id="exportImportRegistry",
)
router.add_api_route(
    "/imports/{import_id}",
    handlers.get_import,
    methods=["GET"],
    response_model=ImportDetail,
    summary="Read an import and its audit trail",
    operation_id="getImport",
)
router.add_api_route(
    "/imports/{import_id}/comparison",
    handlers.get_import_comparison,
    methods=["GET"],
    response_model=ImportComparisonResponse,
    summary="Compare an import with the prior approved version",
    operation_id="compareImport",
)
router.add_api_route(
    "/imports/{import_id}/source",
    handlers.get_import_source,
    methods=["GET"],
    response_model=None,
    summary="Download the exact original workbook",
    operation_id="downloadImportSource",
)
router.add_api_route(
    "/source-rows/{source_row_id}/preview",
    handlers.source_row_preview,
    methods=["GET"],
    response_model=SourcePreviewResponse,
    summary="Read an exact source row centered on a workbook cell",
    operation_id="previewSourceRow",
)
router.add_api_route(
    "/imports/{import_id}/approve",
    handlers.approve,
    methods=["POST"],
    response_model=ImportDetail,
    summary="Independently approve a validated import",
    operation_id="approveImport",
)
router.add_api_route(
    "/imports/{import_id}/reject",
    handlers.reject,
    methods=["POST"],
    response_model=ImportDetail,
    summary="Reject an import without deleting evidence",
    operation_id="rejectImport",
)
router.add_api_route(
    "/imports/{import_id}/withdraw",
    handlers.withdraw,
    methods=["POST"],
    response_model=ImportDetail,
    summary="Withdraw a published version without deleting its evidence",
    operation_id="withdrawImport",
)
router.add_api_route(
    "/imports/{import_id}/publish",
    handlers.publish,
    methods=["POST"],
    response_model=ImportDetail,
    summary="Publish an independently approved version",
    operation_id="publishImport",
)
router.add_api_route(
    "/reference-data/classes-and-ratings",
    handlers.get_reference_dictionary_status,
    methods=["GET"],
    response_model=ReferenceDictionaryStatus,
    summary="Read the current instrument classification/ratings dictionary status",
    operation_id="getReferenceDictionaryStatus",
)
router.add_api_route(
    "/reference-data/classes-and-ratings",
    handlers.upload_reference_dictionary,
    methods=["POST"],
    response_model=ReferenceDictionaryUploadResponse,
    summary="Replace the instrument classification/ratings dictionary",
    operation_id="uploadReferenceDictionary",
)
router.add_api_route(
    "/reference-data/dividends",
    handlers.get_dividend_data_status,
    methods=["GET"],
    response_model=DividendDataStatus,
    summary="Read dividend reference-data freshness",
    operation_id="getDividendDataStatus",
)
router.add_api_route(
    "/reference-data/dividends",
    handlers.upload_dividend_data,
    methods=["POST"],
    response_model=DividendDataUploadResponse,
    summary="Replace the Bloomberg dividend reference file",
    operation_id="uploadDividendData",
)
