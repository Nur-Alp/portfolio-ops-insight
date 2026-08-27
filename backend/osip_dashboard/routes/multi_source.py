"""Generic multi-source upload workflow and domain read APIs."""

from __future__ import annotations

import re
from typing import Annotated, Any, Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from osip_dashboard.api_schemas import (
    ApprovalRequest,
    DatasetMaterializeRequest,
    DatasetVersionList,
    DatasetVersionResponse,
    DatasetMappingResponse,
    MappingConfirmationRequest,
    ClientIdentityExceptionList,
    ClientIdentityResolveRequest,
    DatasetComparisonResponse,
    ModuleReadResponse,
    OperationsReadinessResponse,
    RejectionRequest,
    SourceUploadResponse,
    SessionContextResponse,
    WithdrawalRequest,
)
from osip_dashboard.identity import get_actor, require_domain, require_portfolio, require_role
from osip_dashboard.i18n import localize_dataset_issue, localize_text, request_language
from osip_dashboard.ingestion.multi_source import SourceDetectionError
from osip_dashboard.persistence.models import DatasetRecord, DatasetVersion, ImportBatch, ImportStatus, ReconciliationResult, SourceUpload
from osip_dashboard.services.multi_source_export import create_module_xlsx
from osip_dashboard.services.brokerage import is_repo_trade
from osip_dashboard.services.multi_source import (
    approve_dataset,
    create_source_upload,
    confirm_dataset_mapping,
    compare_datasets,
    dataset_mapping,
    list_client_identity_exceptions,
    resolve_client_identity,
    dataset_manifest,
    get_dataset,
    list_datasets,
    latest_published,
    materialize_datasets,
    module_payload,
    publish_dataset,
    readiness_register,
    record_dataset_event,
    reject_dataset,
    withdraw_dataset,
)
from osip_dashboard.services.workflow import Actor


router = APIRouter(tags=["multi-source"])


def _session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(_session)]
ActorDep = Annotated[Actor, Depends(get_actor)]


@router.get("/session/context", response_model=SessionContextResponse, operation_id="getSessionContext")
def session_context(actor: ActorDep) -> dict[str, object]:
    """Expose the effective scopes so the UI can hide unrelated workspaces."""
    require_role(actor, "reader")
    return {
        "actor_id": actor.actor_id,
        "roles": sorted(actor.roles),
        "domains": sorted(actor.domains),
        "portfolios": sorted(actor.portfolios),
    }


@router.post("/source-uploads", response_model=SourceUploadResponse, status_code=201, operation_id="createSourceUpload")
async def upload_source(response: Response, request: Request, session: SessionDep, actor: ActorDep, file: UploadFile = File(...)):
    require_role(actor, "uploader")
    limit = request.app.state.settings.max_upload_bytes
    content = await file.read(limit + 1)
    try:
        upload, duplicate = create_source_upload(session, request.app.state.blob_store, filename=file.filename or "", content=content, uploader_id=actor.actor_id, max_upload_bytes=limit)
        require_domain(actor, _source_upload_domain(upload.detected_source_type))
        session.commit()
    except SourceDetectionError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if duplicate: response.status_code = 200
    return _upload_payload(upload, duplicate)


@router.get("/source-uploads/{upload_id}", response_model=SourceUploadResponse, operation_id="getSourceUpload")
def source_upload_detail(upload_id: UUID, session: SessionDep, actor: ActorDep):
    require_role(actor, "reader")
    upload = session.get(SourceUpload, upload_id)
    if upload is None: raise HTTPException(status_code=404, detail="Загрузка источника не найдена")
    require_domain(actor, _source_upload_domain(upload.detected_source_type))
    if not _actor_can_read_uploader_id(actor, upload.uploader_id):
        raise HTTPException(status_code=403, detail="Нет доступа к наборам этого источника")
    return _upload_payload(upload, False)


@router.get("/source-uploads/{upload_id}/source", operation_id="downloadSourceUpload")
def download_source_upload(upload_id: UUID, request: Request, session: SessionDep, actor: ActorDep) -> FileResponse:
    require_role(actor, "reader")
    upload = session.get(SourceUpload, upload_id)
    if upload is None: raise HTTPException(status_code=404, detail="Загрузка источника не найдена")
    require_domain(actor, _source_upload_domain(upload.detected_source_type))
    if not _actor_can_read_uploader_id(actor, upload.uploader_id):
        raise HTTPException(status_code=403, detail="Нет доступа к наборам этого источника")
    path = request.app.state.blob_store.path_for(upload.storage_key)
    if not path.exists(): raise HTTPException(status_code=404, detail="Сохранённый файл источника недоступен")
    for dataset in upload.datasets:
        if _has_dataset_access(actor, dataset): record_dataset_event(session, dataset, actor.actor_id, "source.downloaded", {"source_upload_id": str(upload.id)})
    session.commit()
    media = "application/vnd.ms-excel" if upload.file_format == "xls" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(path, media_type=media, filename=upload.original_filename)


@router.post("/source-uploads/{upload_id}/datasets", response_model=DatasetVersionList, operation_id="materializeSourceDatasets")
def create_datasets(upload_id: UUID, body: DatasetMaterializeRequest, request: Request, session: SessionDep, actor: ActorDep):
    require_role(actor, "uploader")
    upload = session.get(SourceUpload, upload_id)
    if upload is None: raise HTTPException(status_code=404, detail="Загрузка источника не найдена")
    if upload.uploader_id != actor.actor_id:
        raise HTTPException(status_code=403, detail="Разобрать наборы данных может только загрузивший источник оператор")
    proposals = {str(item.get("key")): item for item in upload.detection.get("datasets", [])}
    for assignment in body.datasets:
        proposal = proposals.get(assignment.detected_key)
        if proposal is not None:
            require_domain(actor, _dataset_domain(str(proposal.get("dataset_type") or "")))
            if str(proposal.get("scope_type") or "") in {"portfolio", "fund"}:
                require_portfolio(actor, assignment.scope_code or proposal.get("scope_code"))
    try:
        datasets = materialize_datasets(session, request.app.state.blob_store, upload, assignments=[item.model_dump() for item in body.datasets], uploader_id=actor.actor_id)
        if request.app.state.settings.source_first_mode:
            # Source-backed domain datasets are read-only presentation inputs.
            # Make them visible immediately while retaining every DQ finding,
            # source reference and audit event. OSIP remains on its explicit
            # portfolio-assignment workflow.
            for dataset in datasets:
                if dataset.status == ImportStatus.VALIDATED:
                    publish_dataset(session, dataset, "source-system", source_first=True)
        for dataset in datasets: _require_dataset_access(actor, dataset)
        session.commit()
        datasets = [get_dataset(session, item.id) for item in datasets]
    except (SourceDetectionError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        # In source_first_mode (this app's actual deployed mode - see
        # config.py), this is the primary publish path: materialize calls
        # publish_dataset directly for every validated dataset, not through
        # the separate /publish endpoint that already catches this same
        # race (see dataset_publish above). A concurrent materialize for
        # the same key can lose either that publish race or
        # _add_with_version_retry's own bounded retry (uq_dataset_scope_date_version,
        # uq_published_dataset_scope_date) - same underlying guarantee,
        # same clean-409 treatment instead of an unhandled 500.
        session.rollback()
        raise HTTPException(status_code=409, detail="Набор уже создан или опубликован в другой версии; обновите страницу") from exc
    return {"items": [_dataset_payload(item, request_language(request)) for item in datasets if item is not None]}


@router.get("/dataset-versions", response_model=DatasetVersionList, operation_id="listDatasetVersions")
def dataset_list(request: Request, session: SessionDep, actor: ActorDep, dataset_type: str | None = Query(None), scope_code: str | None = Query(None)):
    require_role(actor, "reader")
    datasets = [item for item in list_datasets(session, dataset_type=dataset_type, scope_code=scope_code) if _has_dataset_access(actor, item)]
    return {"items": [_dataset_payload(item, request_language(request)) for item in datasets]}


@router.get("/dataset-versions/{dataset_id}", response_model=DatasetVersionResponse, operation_id="getDatasetVersion")
def dataset_detail(dataset_id: UUID, request: Request, session: SessionDep, actor: ActorDep):
    require_role(actor, "reader")
    dataset = _load_authorized_dataset(session, actor, dataset_id)
    return _dataset_payload(dataset, request_language(request))


@router.get("/dataset-versions/{dataset_id}/mapping", response_model=DatasetMappingResponse, operation_id="getDatasetMapping")
def dataset_mapping_detail(dataset_id: UUID, session: SessionDep, actor: ActorDep) -> dict[str, object]:
    require_role(actor, "reader")
    dataset = _load_authorized_dataset(session, actor, dataset_id)
    return dataset_mapping(dataset)


@router.get("/dataset-versions/{dataset_id}/compare", response_model=DatasetComparisonResponse, operation_id="compareDatasetVersions")
def dataset_compare(dataset_id: UUID, session: SessionDep, actor: ActorDep, with_id: UUID = Query(..., alias="with_id")) -> dict[str, object]:
    require_role(actor, "reader")
    left = _load_authorized_dataset(session, actor, dataset_id)
    right = _load_authorized_dataset(session, actor, with_id)
    try:
        return compare_datasets(left, right)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/dataset-versions/{dataset_id}/mapping/confirm", response_model=DatasetMappingResponse, operation_id="confirmDatasetMapping")
def dataset_mapping_confirm(dataset_id: UUID, body: MappingConfirmationRequest, session: SessionDep, actor: ActorDep) -> dict[str, object]:
    require_role(actor, "reviewer")
    dataset = _load_authorized_dataset(session, actor, dataset_id)
    try:
        confirm_dataset_mapping(session, dataset, actor.actor_id, body.comment)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return dataset_mapping(_load_authorized_dataset(session, actor, dataset_id))


@router.get("/client-exceptions", response_model=ClientIdentityExceptionList, operation_id="listClientIdentityExceptions")
def client_identity_exceptions(session: SessionDep, actor: ActorDep, status_filter: str = Query("pending", alias="status")) -> dict[str, object]:
    require_role(actor, "reader")
    require_domain(actor, "client_ops")
    if status_filter not in {"pending", "confirmed", "rejected", "all"}:
        raise HTTPException(status_code=422, detail="Недопустимый статус исключения")
    return {"items": list_client_identity_exceptions(session, status_filter, uploader_id=_uploader_filter(actor))}


@router.post("/client-exceptions/{record_id}/resolve", response_model=dict, operation_id="resolveClientIdentityException")
def client_identity_exception_resolve(record_id: UUID, body: ClientIdentityResolveRequest, session: SessionDep, actor: ActorDep) -> dict[str, object]:
    require_role(actor, "reviewer")
    require_domain(actor, "client_ops")
    record = session.get(DatasetRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Исключение идентичности клиента не найдено")
    _require_dataset_access(actor, record.dataset)
    try:
        result = resolve_client_identity(session, record_id, actor.actor_id, body.disposition, body.account, body.comment)
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/dataset-versions/{dataset_id}/approve", response_model=DatasetVersionResponse, operation_id="approveDatasetVersion")
def dataset_approve(dataset_id: UUID, body: ApprovalRequest, request: Request, session: SessionDep, actor: ActorDep):
    require_role(actor, "reviewer")
    dataset = _load_authorized_dataset(session, actor, dataset_id)
    try:
        approve_dataset(
            session,
            dataset,
            actor.actor_id,
            body.comment,
            body.acknowledged_dq_codes,
            mapping_confirmed=body.mapping_confirmed,
        )
        session.commit()
    except ValueError as exc: session.rollback(); raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _dataset_payload(_load_authorized_dataset(session, actor, dataset_id), request_language(request))


@router.post("/dataset-versions/{dataset_id}/reject", response_model=DatasetVersionResponse, operation_id="rejectDatasetVersion")
def dataset_reject(dataset_id: UUID, body: RejectionRequest, request: Request, session: SessionDep, actor: ActorDep):
    require_role(actor, "reviewer")
    dataset = _load_authorized_dataset(session, actor, dataset_id)
    try: reject_dataset(session, dataset, actor.actor_id, body.reason); session.commit()
    except ValueError as exc: session.rollback(); raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _dataset_payload(_load_authorized_dataset(session, actor, dataset_id), request_language(request))


@router.post("/dataset-versions/{dataset_id}/publish", response_model=DatasetVersionResponse, operation_id="publishDatasetVersion")
def dataset_publish(dataset_id: UUID, request: Request, session: SessionDep, actor: ActorDep):
    require_role(actor, "publisher")
    dataset = _load_authorized_dataset(session, actor, dataset_id)
    try:
        publish_dataset(session, dataset, actor.actor_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        # publish_dataset supersedes any prior published row for the same
        # (dataset_type, scope_code, business_date, uploader_id) key before
        # writing the new one, but only within this transaction - two
        # concurrent publish requests for the same key can both pass that
        # check before either commits. uq_published_dataset_scope_date (a
        # partial unique index, see persistence/models.py) is the actual
        # race-safety guarantee; this just turns its violation into the same
        # clean 409 a sequential conflict already gets, instead of a 500.
        # Mirrors the identical pattern in services/imports.py's OSIP upload race.
        session.rollback()
        raise HTTPException(status_code=409, detail="Набор уже опубликован в другой версии; обновите страницу") from exc
    return _dataset_payload(_load_authorized_dataset(session, actor, dataset_id), request_language(request))


@router.post("/dataset-versions/{dataset_id}/withdraw", response_model=DatasetVersionResponse, operation_id="withdrawDatasetVersion")
def dataset_withdraw(dataset_id: UUID, body: WithdrawalRequest, request: Request, session: SessionDep, actor: ActorDep):
    require_role(actor, "publisher")
    dataset = _load_authorized_dataset(session, actor, dataset_id)
    try: withdraw_dataset(session, dataset, actor.actor_id, body.reason); session.commit()
    except ValueError as exc: session.rollback(); raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _dataset_payload(_load_authorized_dataset(session, actor, dataset_id), request_language(request))


for path, module, operation in (
    ("/funds/TABYS/overview", "asset-management", "getFundOverview"),
    ("/funds/TABYS/holdings", "asset-management", "getFundHoldings"),
    ("/funds/TABYS/unit-history", "asset-management", "getFundUnitHistory"),
    ("/treasury/overview", "treasury", "getTreasuryOverview"),
    ("/brokerage/overview", "brokerage", "getBrokerageOverview"),
    ("/brokerage/trades", "brokerage", "getBrokerageTrades"),
    ("/brokerage/derivatives", "brokerage", "getBrokerageDerivatives"),
    ("/clients", "clients", "listClients"),
    ("/corporate-finance/overview", "corporate-finance", "getCorporateFinanceOverview"),
    ("/corporate-finance/deals", "corporate-finance", "listCorporateFinanceDeals"),
    ("/accounting/source-readiness", "accounting", "getAccountingSourceReadiness"),
    ("/risk/overview", "risk", "getRiskOverview"),
):
    def make_endpoint(selected_module: str):
        def endpoint(
            request: Request,
            session: SessionDep,
            actor: ActorDep,
            dataset_versions: list[UUID] = Query(default=[]),
            source_upload_id: UUID | None = Query(default=None),
        ):
            require_role(actor, "reader")
            require_domain(actor, _module_domain(selected_module))
            if selected_module == "asset-management":
                require_portfolio(actor, "TABYS")
            elif selected_module == "treasury":
                require_portfolio(actor, "SOBSTV")
            # Asset Management is fed by two genuinely independent physical
            # workbooks (valuation/holdings vs. unit-value history - see
            # module_payload's asset-management branch), so it alone needs
            # both a whole-package pin (source_upload_id, for the valuation
            # family) and an independent per-type override (dataset_versions,
            # for fund_unit_series) in the same request. Every other module's
            # "package" is genuinely one file, so combining both there would
            # only ever be user error - keep rejecting it for them.
            version_overrides = _resolve_version_overrides(session, actor, selected_module, dataset_versions, source_upload_id)
            if source_upload_id is not None:
                if selected_module == "treasury":
                    batches = list(session.scalars(select(ImportBatch).where(
                        ImportBatch.source_upload_id == source_upload_id,
                        ImportBatch.portfolio_code == "SOBSTV",
                        ImportBatch.status.in_((ImportStatus.PUBLISHED, ImportStatus.SUPERSEDED)),
                    )))
                    candidates = []
                    # ImportBatch isn't a DatasetVersion, so it can't go
                    # through _require_dataset_access below like every other
                    # module's candidates do - same per-uploader visibility
                    # rule enforced directly here instead. Treated as "not
                    # found" (matching the empty-batches case above) rather
                    # than 403, since a batch belonging to another uploader
                    # should read the same as a source_upload_id that never
                    # matched a Treasury workbook at all.
                    if not batches or not any(_actor_can_read_uploader_id(actor, batch.uploader_id) for batch in batches):
                        raise HTTPException(status_code=404, detail="Версия рабочей книги не найдена")
                else:
                    candidates = list(session.scalars(select(DatasetVersion).where(DatasetVersion.source_upload_id == source_upload_id)))
                if not candidates:
                    if selected_module != "treasury":
                        raise HTTPException(status_code=404, detail="Версия рабочей книги не найдена")
                for dataset in candidates:
                    _require_dataset_access(actor, dataset)
            payload = module_payload(
                session,
                selected_module,
                request_language(request),
                version_overrides=version_overrides,
                source_upload_id=source_upload_id,
                uploader_id=_uploader_filter(actor),
            )
            if source_upload_id is not None and not payload["sources"]:
                raise HTTPException(status_code=409, detail="Выбранная рабочая книга не содержит данных для этой области")
            return payload
        return endpoint
    router.add_api_route(path, make_endpoint(module), methods=["GET"], response_model=ModuleReadResponse, operation_id=operation)


@router.get("/clients/records/{record_id}", response_model=ModuleReadResponse, operation_id="getClientAccount")
def client_detail(record_id: UUID, session: SessionDep, actor: ActorDep):
    require_role(actor, "reader")
    require_domain(actor, "client_ops")
    record = session.scalar(select(DatasetRecord).join(DatasetVersion).where(
        DatasetRecord.id == record_id,
        DatasetVersion.dataset_type == "client_account_snapshot",
        DatasetVersion.status == ImportStatus.PUBLISHED,
    ))
    if record is None:
        raise HTTPException(status_code=404, detail="Клиентская запись не найдена")
    _require_dataset_access(actor, record.dataset)
    payload = module_payload(session, "clients", uploader_id=_uploader_filter(actor))
    account = record.payload.get("account")
    client_name = str(record.payload.get("client_name") or "")
    normalized_name = re.sub(r"\s+", " ", client_name).strip().casefold()
    for key, rows in list(payload["records"].items()):
        if key == "client_dashboard_snapshot":
            payload["records"][key] = [
                row for row in rows
                if re.sub(r"\s+", " ", str(row.get("client_name") or "")).strip().casefold() == normalized_name
            ]
        else:
            payload["records"][key] = [row for row in rows if row.get("account") == account]
    record_dataset_event(session, record.dataset, actor.actor_id, "client_detail.read", {"record_count": sum(len(rows) for rows in payload["records"].values())})
    session.commit()
    return payload


@router.get("/funds/TABYS/export", operation_id="exportFundData")
def export_fund(
    session: SessionDep,
    actor: ActorDep,
    term: str = Query("", max_length=200),
    dataset_versions: list[UUID] = Query(default=[]),
    source_upload_id: UUID | None = Query(default=None),
) -> Response:
    version_overrides = _resolve_version_overrides(session, actor, "asset-management", dataset_versions, source_upload_id)
    return _module_export(
        session, actor, "asset-management", "PortfolioOpsInsight_fund_TABYS.xlsx", term=term,
        source_upload_id=source_upload_id, version_overrides=version_overrides,
    )


@router.get("/brokerage/export", operation_id="exportBrokerageData")
def export_brokerage(
    session: SessionDep,
    actor: ActorDep,
    term: str = Query("", max_length=200),
    include_repo: bool = Query(True),
    source_upload_id: UUID | None = Query(default=None),
) -> Response:
    """Export the same physical brokerage workbook package shown in the UI.

    When a historical workbook is selected in the domain version bar, every
    child dataset in this export must come from that upload.  It is safer to
    omit a missing child than to silently add its latest version from another
    workbook package.
    """
    return _module_export(
        session,
        actor,
        "brokerage",
        "PortfolioOpsInsight_brokerage.xlsx",
        term=term,
        include_repo=include_repo,
        source_upload_id=source_upload_id,
    )


@router.get("/corporate-finance/export", operation_id="exportCorporateFinanceData")
def export_corporate_finance(session: SessionDep, actor: ActorDep, term: str = Query("", max_length=200)) -> Response:
    return _module_export(session, actor, "corporate-finance", "PortfolioOpsInsight_corporate_finance.xlsx", term=term)


@router.get("/risk/export", operation_id="exportRiskData")
def export_risk(
    session: SessionDep,
    actor: ActorDep,
    term: str = Query("", max_length=200),
    dataset_versions: list[UUID] = Query(default=[]),
) -> Response:
    # Risk has no whole-package pin (SOBSTV/TABYS are independently
    # uploaded), only the per-scope pickers dataset_versions covers.
    version_overrides = _resolve_version_overrides(session, actor, "risk", dataset_versions, None)
    return _module_export(session, actor, "risk", "PortfolioOpsInsight_risk.xlsx", term=term, version_overrides=version_overrides)


@router.get("/accounting/export", operation_id="exportAccountingData")
def export_accounting(
    session: SessionDep,
    actor: ActorDep,
    term: str = Query("", max_length=200),
    dataset_versions: list[UUID] = Query(default=[]),
) -> Response:
    version_overrides = _resolve_version_overrides(session, actor, "accounting", dataset_versions, None)
    return _module_export(session, actor, "accounting", "PortfolioOpsInsight_accounting.xlsx", term=term, version_overrides=version_overrides)


@router.get("/operations/source-readiness", response_model=OperationsReadinessResponse, operation_id="getOperationsSourceReadiness")
def operations_readiness(request: Request, session: SessionDep, actor: ActorDep):
    require_role(actor, "reader")
    datasets = [item for item in list_datasets(session) if _has_dataset_access(actor, item)]
    allowed_ids = {str(item.id) for item in datasets}
    reconciliations = list(session.scalars(select(ReconciliationResult).order_by(ReconciliationResult.created_at.desc()).limit(100)))
    reconciliations = [item for item in reconciliations if not item.dataset_ids or any(identifier in allowed_ids for identifier in item.dataset_ids)]
    return {
        "datasets": [_dataset_payload(item, request_language(request)) for item in datasets],
        "reconciliations": [{"rule_code": item.rule_code, "scope_code": item.scope_code, "business_date": item.business_date.isoformat() if item.business_date else None, "actual_values": item.actual_values, "difference": str(item.difference) if item.difference is not None else None, "tolerance": str(item.tolerance), "status": item.status, "evidence": item.evidence} for item in reconciliations],
        "readiness": readiness_register(session, uploader_id=_uploader_filter(actor)),
    }


def _module_export(
    session: Session,
    actor: Actor,
    module: str,
    filename: str,
    audit_action: str = "dataset.exported",
    term: str = "",
    include_repo: bool = True,
    source_upload_id: UUID | None = None,
    version_overrides: dict[str, DatasetVersion] | None = None,
) -> Response:
    require_role(actor, "reader")
    require_domain(actor, _module_domain(module))
    mapping = {
        "asset-management": [("fund_valuation", "TABYS"), ("fund_holdings", "TABYS"), ("fund_cash_liabilities", "TABYS"), ("fund_nav_history", "TABYS"), ("fund_prices", "TABYS"), ("fund_unit_series", "TABYS"), ("fund_inactive_evidence", "TABYS")],
        # Brokerage export now also carries the Clients domain (account
        # snapshots, open dates, maturity calendar) so the trading side and
        # the client side of the same book download as one workbook from
        # the Brokerage tab. The Clients tab itself is unaffected - it still
        # reads client_account_snapshot etc. directly, it just has no export
        # button of its own anymore.
        "brokerage": [("brokerage_trade_ledger", "BROKERAGE"), ("derivatives_register", "BROKERAGE"), ("client_account_snapshot", "BROKERAGE"), ("client_open_dates", "BROKERAGE"), ("client_maturity_calendar", "BROKERAGE"), ("client_dashboard_snapshot", "BROKERAGE")],
        "corporate-finance": [("corporate_finance_register", "CORPFIN")],
        "risk": [("risk_limits_sobstv", "SOBSTV"), ("risk_limits_tabys", "TABYS")],
        "accounting": [("accounting_balance_sheet", "ACCOUNTING"), ("accounting_income_statement", "ACCOUNTING"), ("accounting_budget", "ACCOUNTING"), ("accounting_portfolio_detail", "ACCOUNTING")],
    }
    if source_upload_id is None:
        datasets = [dataset for dataset_type, scope in mapping[module] if (dataset := latest_published(session, dataset_type, scope, uploader_id=_uploader_filter(actor)))]
    else:
        expected = mapping[module]
        candidates = list(session.scalars(
            select(DatasetVersion).options(
                selectinload(DatasetVersion.source_upload),
                selectinload(DatasetVersion.records),
                selectinload(DatasetVersion.issues),
            ).where(
                DatasetVersion.source_upload_id == source_upload_id,
                DatasetVersion.status.in_([ImportStatus.PUBLISHED, ImportStatus.SUPERSEDED]),
            ).order_by(DatasetVersion.created_at.desc())
        ))
        # A physical workbook can contain more than one child of a type.  The
        # newest retained child wins, but only when it also matches the
        # expected scope.  This preserves the selected package boundary.
        by_key: dict[tuple[str, str], DatasetVersion] = {}
        for dataset in candidates:
            by_key.setdefault((dataset.dataset_type, dataset.scope_code), dataset)
        datasets = [
            by_key[(dataset_type, scope)]
            for dataset_type, scope in expected
            if (dataset_type, scope) in by_key
        ]
    if version_overrides:
        # A pinned older workbook version in the domain-version bar (Risk's
        # per-scope picker, Accounting's per-statement picker, Asset
        # Management's fund_unit_series override) used to be silently
        # ignored here - the export always regenerated from latest_published
        # regardless, so "pin an old version, hit Export" produced a
        # workbook that disagreed with what was on screen. Overriding by
        # dataset_type on top of whichever resolution ran above (matching
        # module_payload's own override-merging for the read side) fixes
        # both the plain case and the source_upload_id+dataset_versions
        # combination Asset Management alone is allowed to send.
        by_type = {dataset.dataset_type: dataset for dataset in datasets}
        by_type.update(version_overrides)
        datasets = [by_type[dataset_type] for dataset_type, _scope in mapping[module] if dataset_type in by_type]
    if not datasets:
        raise HTTPException(status_code=409, detail="Нет опубликованных наборов данных для выгрузки")
    for dataset in datasets: _require_dataset_access(actor, dataset)
    content = create_module_xlsx(module, datasets, term=term, include_repo=include_repo)
    for dataset in datasets:
        record_dataset_event(
            session,
            dataset,
            actor.actor_id,
            audit_action,
            {
                "format": "xlsx",
                "filename": filename,
                "term": term,
                "include_repo": include_repo,
                "source_upload_id": str(source_upload_id) if source_upload_id else None,
                "row_count": _filtered_record_count(dataset, term, include_repo=include_repo),
            },
        )
    session.commit()
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _filtered_record_count(dataset: DatasetVersion, term: str, *, include_repo: bool = True) -> int:
    normalized = term.strip().casefold()
    if not normalized:
        return len(dataset.records)
    return sum(
        1
        for record in dataset.records
        if any(normalized in str(value).casefold() for value in record.payload.values())
        and (include_repo or not is_repo_trade(record.payload))
    )


def _required_dataset(session: Session, dataset_id: UUID) -> DatasetVersion:
    dataset = get_dataset(session, dataset_id)
    if dataset is None: raise HTTPException(status_code=404, detail="Набор данных не найден")
    return dataset


def _resolve_version_overrides(
    session: Session, actor: Actor, selected_module: str, dataset_versions: list[UUID], source_upload_id: UUID | None
) -> dict[str, DatasetVersion]:
    """Shared by the read endpoints and the export endpoints so a pinned
    version means the same thing in both places - see _module_export's own
    comment on why this used to only apply to what you see on screen, never
    to what "Export" downloaded.
    """
    if dataset_versions and source_upload_id is not None and selected_module != "asset-management":
        raise HTTPException(status_code=400, detail="Выберите либо отдельные версии, либо единую версию рабочей книги")
    version_overrides: dict[str, DatasetVersion] = {}
    for dataset_id in dataset_versions:
        pinned = _load_authorized_dataset(session, actor, dataset_id)
        version_overrides[pinned.dataset_type] = pinned
    return version_overrides


def _load_authorized_dataset(session: Session, actor: Actor, dataset_id: UUID) -> DatasetVersion:
    """Load a dataset and enforce access in one call - use this everywhere a
    single dataset needs to be fetched by id, instead of chaining
    ``_required_dataset``/``_require_dataset_access`` by hand. Making the
    check part of the load itself, rather than a second call a future edit
    could omit, is what actually closes this class of bug: the leaks fixed
    in 2dadb42 (treasury overview, client identity exceptions) were both
    missing checks, not incorrect ones.
    """
    dataset = _required_dataset(session, dataset_id)
    _require_dataset_access(actor, dataset)
    return dataset


def _actor_can_read_uploader_id(actor: Actor, uploader_id: str) -> bool:
    """The read half of the per-uploader visibility rule, shared by every
    call site that checks "does this actor's identity match the uploader"
    (DatasetVersion below, but also SourceUpload's own detail/download
    routes, which store uploader_id directly rather than via a dataset).
    See docs/domain-upload-instructions.md "Visibility rule": a normal
    domain operator sees only what they themselves uploaded, even sharing a
    domain/portfolio with a colleague who uploaded something else. The
    "admin" role is the deliberate, explicit governance bypass described
    there - a broad domain claim (``domains: ["*"]``) alone still does not
    grant it; only this specific role does. Write actions on someone else's
    raw upload (e.g. materializing datasets) are deliberately NOT covered by
    this bypass - it only ever widens what "admin" can see, never what it
    can do to another operator's in-flight upload.
    """
    return "admin" in actor.roles or uploader_id == actor.actor_id


def _uploader_filter(actor: Actor) -> str | None:
    """The uploader_id to pass into the *_id-filtered read queries
    (module_payload, latest_published, readiness_register, etc.) - those
    filter at the SQL level rather than post-checking each row through
    _actor_can_read_uploader_id, so the admin bypass has to be applied here
    instead: None means "no uploader filter", i.e. every uploader's data.
    """
    return None if "admin" in actor.roles else actor.actor_id


def _has_uploader_access(actor: Actor, dataset: DatasetVersion) -> bool:
    return _actor_can_read_uploader_id(actor, dataset.uploader_id)


def _has_dataset_access(actor: Actor, dataset: DatasetVersion) -> bool:
    domain = _dataset_domain(dataset.dataset_type)
    domain_allowed = "*" in actor.domains or domain is None or domain in actor.domains
    portfolio_allowed = dataset.scope_type not in {"portfolio", "fund"} or "*" in actor.portfolios or dataset.scope_code.upper() in actor.portfolios
    return domain_allowed and portfolio_allowed and _has_uploader_access(actor, dataset)


def _require_dataset_access(actor: Actor, dataset: DatasetVersion) -> None:
    require_domain(actor, _dataset_domain(dataset.dataset_type))
    if dataset.scope_type in {"portfolio", "fund"}:
        require_portfolio(actor, dataset.scope_code)
    if not _has_uploader_access(actor, dataset):
        raise HTTPException(status_code=403, detail="Нет доступа к наборам данных другого оператора")


def _module_domain(module: str) -> str | None:
    return {
        "asset-management": "back_office",
        "treasury": "back_office",
        "brokerage": "client_ops",
        "clients": "client_ops",
        "corporate-finance": "corpfin",
        "accounting": "accounting",
        "risk": "risk",
    }.get(module)


def _dataset_domain(dataset_type: str) -> str | None:
    if dataset_type == "portfolio_snapshot" or dataset_type.startswith("fund_"):
        return "back_office"
    if dataset_type in {"client_account_snapshot", "brokerage_trade_ledger", "derivatives_register", "client_open_dates", "client_maturity_calendar", "client_dashboard_snapshot"}:
        return "client_ops"
    if dataset_type == "corporate_finance_register":
        return "corpfin"
    if dataset_type in {"accounting_landing", "accounting_balance_sheet", "accounting_income_statement", "accounting_budget", "accounting_portfolio_detail"}:
        return "accounting"
    if dataset_type.startswith("risk_"):
        return "risk"
    return None


def _source_upload_domain(source_type: str) -> str | None:
    """Resolve access before child datasets exist, using detected structure only."""
    if source_type in {"tabys_valuation", "fund_unit_history", "osip_portfolio"}:
        return "back_office"
    if source_type == "client_brokerage":
        return "client_ops"
    if source_type == "corporate_finance":
        return "corpfin"
    if source_type.startswith("accounting_"):
        return "accounting"
    if source_type.startswith("risk_"):
        return "risk"
    return None


def _upload_payload(upload: SourceUpload, duplicate: bool) -> dict:
    children = [{"id": str(item.id), "dataset_type": item.dataset_type, "scope_code": item.scope_code, "business_date": item.business_date.isoformat() if item.business_date else None, "version": item.version, "status": item.status.value} for item in upload.datasets]
    progress: dict[str, int] = {}
    for item in children:
        status = str(item["status"])
        progress[status] = progress.get(status, 0) + 1
    return {"id": str(upload.id), "duplicate": duplicate, "source_sha256": upload.source_sha256, "original_filename": upload.original_filename, "file_format": upload.file_format, "detected_source_type": upload.detected_source_type, "sheets": upload.detection.get("sheets", []), "datasets": upload.detection.get("datasets", []), "uploader_id": upload.uploader_id, "created_at": upload.created_at.isoformat(), "children": children, "aggregate_progress": progress}


def _dataset_payload(dataset: DatasetVersion, language: str = "ru") -> dict:
    manifest = dataset_manifest(dataset)
    manifest.pop("dataset_id", None)
    return {**manifest, "id": str(dataset.id), "source_upload_id": str(dataset.source_upload_id), "detected_key": dataset.detected_key, "parser_version": dataset.parser_version, "summary": dataset.summary, "uploader_id": dataset.uploader_id, "reviewer_id": dataset.reviewer_id, "publisher_id": dataset.publisher_id, "review_comment": dataset.review_comment, "rejection_reason": dataset.rejection_reason, "error_message": dataset.error_message, "created_at": dataset.created_at.isoformat(), "issues": [{"id": str(issue.id), "code": issue.code, "severity": issue.severity, "message": localize_dataset_issue(issue.code, issue.message, language), "affected_fields": issue.affected_fields, "source_refs": issue.source_refs, "acknowledged_by": issue.acknowledged_by} for issue in dataset.issues]}
