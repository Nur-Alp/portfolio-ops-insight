"""Versioned HTTP request and response contracts for the OSIP API.

Financial values intentionally remain strings at the API boundary. These models
are also the authoritative source for the generated OpenAPI document.
"""

from __future__ import annotations

from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


Basis = Literal["source", "derived", "unavailable"]
ImportState = Literal[
    "draft",
    "validating",
    "validated",
    "approved",
    "published",
    "failed",
    "rejected",
    "superseded",
    "withdrawn",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetAssignment(ContractModel):
    detected_key: str = Field(min_length=1, max_length=120)
    scope_code: str | None = Field(default=None, max_length=120)
    # Only meaningful for accounting_portfolio_detail: which OSIP portfolio
    # (SOBSTV/TABYS) this accounting workbook should be reconciled against.
    # The source data does not state this explicitly, so it is never
    # inferred - see materialize_datasets.
    reconciliation_portfolio_code: str | None = Field(default=None, max_length=120)


class DatasetMaterializeRequest(ContractModel):
    datasets: list[DatasetAssignment] = Field(min_length=1)


class SourceDatasetProposal(ContractModel):
    key: str
    dataset_type: str
    scope_type: str
    scope_code: str


class SourceUploadResponse(ContractModel):
    id: str
    duplicate: bool = False
    source_sha256: str
    original_filename: str
    file_format: str
    detected_source_type: str
    sheets: list[str]
    datasets: list[SourceDatasetProposal]
    uploader_id: str
    created_at: str
    children: list[dict[str, Any]] = Field(default_factory=list)
    aggregate_progress: dict[str, int] = Field(default_factory=dict)


class GenericDatasetIssue(ContractModel):
    id: str
    code: str
    severity: str
    message: str
    affected_fields: list[str]
    source_refs: list[dict[str, Any]]
    acknowledged_by: str | None


class DatasetVersionResponse(ContractModel):
    id: str
    source_upload_id: str | None = None
    dataset_type: str
    detected_key: str
    scope_type: str
    scope_code: str
    source_report_date: str | None
    business_date: str | None
    parser_version: str
    generated_at: str | None = None
    freshness: str = "unavailable"
    dq_blocker_count: int = 0
    dq_high_count: int = 0
    version: int
    status: ImportState
    summary: dict[str, Any]
    source_filename: str
    uploader_id: str
    reviewer_id: str | None
    publisher_id: str | None
    review_comment: str | None
    rejection_reason: str | None
    error_message: str | None
    created_at: str
    issues: list[GenericDatasetIssue]


class DatasetVersionList(ContractModel):
    items: list[DatasetVersionResponse]


class SessionContextResponse(ContractModel):
    actor_id: str
    roles: list[str]
    domains: list[str]
    portfolios: list[str]


class DatasetMappingField(ContractModel):
    normalized_field: str
    source_header: str | None = None
    source_sheet: str | None = None
    source_row: int | None = None
    source_column: int | None = None
    sample_values: list[str] = Field(default_factory=list)


class DatasetMappingResponse(ContractModel):
    dataset_id: str
    dataset_type: str
    source_filename: str
    confidence: str
    mapping_confirmed: bool
    confirmed_by: str | None = None
    confirmation_comment: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    fields: list[DatasetMappingField] = Field(default_factory=list)


class MappingConfirmationRequest(ContractModel):
    comment: str = Field(min_length=1, max_length=4000)


class ClientIdentityException(ContractModel):
    id: str
    dataset_id: str
    record_id: str
    source_name: str
    normalized_name: str
    source_ref: dict[str, Any]
    original_match_status: str
    status: str
    candidate_accounts: list[str] = Field(default_factory=list)
    resolved_account: str | None = None
    resolved_by: str | None = None
    resolution_comment: str | None = None


class ClientIdentityExceptionList(ContractModel):
    items: list[ClientIdentityException]


class ClientIdentityResolveRequest(ContractModel):
    disposition: Literal["confirmed", "rejected"]
    account: str | None = Field(default=None, max_length=200)
    comment: str = Field(min_length=1, max_length=4000)


class DatasetComparisonResponse(ContractModel):
    left_dataset_id: str
    right_dataset_id: str
    dataset_type: str
    scope_code: str
    business_date: str | None
    added_count: int
    removed_count: int
    changed_count: int
    unchanged_count: int
    added_keys: list[str] = Field(default_factory=list)
    removed_keys: list[str] = Field(default_factory=list)
    changed_keys: list[str] = Field(default_factory=list)
    summary_changes: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ModuleSourceManifest(ContractModel):
    dataset_id: str
    source_upload_id: str
    dataset_type: str
    scope_type: str
    scope_code: str
    source_filename: str
    source_report_date: str | None
    business_date: str | None
    version: int
    status: ImportState
    generated_at: str | None = None
    parser_version: str | None = None
    freshness: str = "unavailable"
    dq_blocker_count: int = 0
    dq_high_count: int = 0


class ModuleReadResponse(ContractModel):
    module: str
    available: bool
    report_date_mismatch: bool
    report_dates: list[str]
    sources: list[ModuleSourceManifest]
    summaries: dict[str, Any]
    records: dict[str, list[dict[str, Any]]]
    disclosure: str
    filename_date_mismatch: bool = False
    pinned_dataset_types: list[str] = []
    selected_source_upload_id: str | None = None
    missing_source_dataset_types: list[str] = []
    history: list[dict[str, Any]] = []
    risk_utilization_history: list[dict[str, Any]] = []
    account_mapping: dict[str, list[dict[str, Any]]] = {}


class ReconciliationRead(ContractModel):
    rule_code: str
    scope_code: str
    business_date: str | None
    actual_values: dict[str, Any]
    difference: str | None
    tolerance: str
    status: str
    evidence: dict[str, Any]


class OperationsReadinessResponse(ContractModel):
    datasets: list[DatasetVersionResponse]
    reconciliations: list[ReconciliationRead]
    readiness: list[dict[str, Any]] = []


class ApprovalRequest(ContractModel):
    comment: str = Field(min_length=1, max_length=4000)
    acknowledged_dq_codes: list[str] = Field(default_factory=list)
    # Trade-ledger mappings must be explicitly confirmed if the source headers
    # are incomplete or ambiguous. Existing datasets with a high-confidence
    # mapping remain backward-compatible with the default False value.
    mapping_confirmed: bool = False


class RejectionRequest(ContractModel):
    reason: str = Field(min_length=1, max_length=4000)


class WithdrawalRequest(ContractModel):
    reason: str = Field(min_length=1, max_length=4000)


class DqAssignmentRequest(ContractModel):
    owner_id: str | None = Field(default=None, max_length=200)
    due_date: str | None = None
    reason: str = Field(min_length=1, max_length=4000)


class DqAssignmentResponse(ContractModel):
    id: str
    owner_id: str | None
    due_date: str | None
    is_overdue: bool


class ExportRequest(ContractModel):
    format: Literal["csv"] = "csv"


class SourceRef(ContractModel):
    workbook_name: str
    sheet_name: str
    row_number: int
    parser_version: str
    source_row_id: str
    # Physical workbook coordinates for the value shown by the UI.  The row
    # reference remains the immutable evidence key; these fields make the
    # source action actionable for a portfolio manager.
    source_column: int | None = None
    source_column_letter: str | None = None
    source_cell: str | None = None
    source_header: str | None = None
    source_kind: Literal["row", "dataset", "workbook"] = "row"
    field: str | None = None
    value: str | None = None
    note: str | None = None


class DQSourceRef(ContractModel):
    workbook_name: str
    sheet_name: str
    row_number: int
    source_columns: list[str] = Field(default_factory=list)
    source_cells: list[str] = Field(default_factory=list)
    source_row_id: str | None = None


class ImportSummary(ContractModel):
    position_count: int
    unique_isin_count: int
    raw_settlement_count: int
    settlement_count: int
    purchase_amount_kzt: str
    derived_carrying_value_kzt: str
    cash_kzt: str
    derived_operational_total_kzt: str


class DQCounts(ContractModel):
    blocker: int
    high: int
    medium: int
    low: int


class AuditEvent(ContractModel):
    id: str
    actor_id: str
    action: str
    detail: dict[str, Any]
    created_at: str


class ImportRecord(ContractModel):
    id: str
    portfolio: str | None
    report_date: str | None
    version: int | None
    status: ImportState
    duplicate: bool
    source_sha256: str
    original_filename: str
    parser_version: str
    uploader_id: str
    reviewer_id: str | None
    publisher_id: str | None
    review_comment: str | None
    rejection_reason: str | None
    error_message: str | None
    created_at: str
    validated_at: str | None
    approved_at: str | None
    published_at: str | None
    snapshot_id: str | None
    summary: ImportSummary | None
    dq_counts: DQCounts
    publication_basis: str = "controlled_workflow"
    publication_requires_override: bool


class ImportDetail(ImportRecord):
    audit_events: list[AuditEvent]


class ImportListResponse(ContractModel):
    items: list[ImportRecord]


class ComparisonIdentity(ContractModel):
    import_id: str
    snapshot_id: str
    portfolio: str
    report_date: str
    version: int
    status: ImportState
    source_sha256: str


class ComparisonMetric(ContractModel):
    current: str | int
    baseline: str | int | None
    delta: str | int | None
    basis: Basis


class LotChange(ContractModel):
    isin: str
    security_code: str
    purchase_date: str | None
    quantity: str
    purchase_price: str | None
    instrument_currency: str
    lot_count: int


class LotChanges(ContractModel):
    added_count: int
    removed_count: int
    unchanged_count: int
    added: list[LotChange]
    removed: list[LotChange]


class ImportComparisonResponse(ContractModel):
    current: ComparisonIdentity
    baseline: ComparisonIdentity | None
    metrics: dict[str, ComparisonMetric]
    lot_changes: LotChanges


class PortfolioItem(ContractModel):
    code: str
    name: str
    reporting_currency: str
    latest_published_report_date: str | None
    latest_published_snapshot_id: str | None


class PortfolioListResponse(ContractModel):
    items: list[PortfolioItem]
    combined_report_dates: list[str]
    report_date_mismatch: bool


class MetricDefinition(ContractModel):
    code: str
    label: str
    basis: Basis
    unit: str | None
    formula: str | None
    version: str
    enabled: bool
    unavailable_reason: str | None


class MetricDefinitionList(ContractModel):
    items: list[MetricDefinition]


class SnapshotSummary(ContractModel):
    id: str
    import_id: str
    source_upload_id: str | None = None
    portfolio: str
    report_date: str
    version: int
    status: ImportState
    value_label: str


class SnapshotListResponse(ContractModel):
    items: list[SnapshotSummary]


class MetricValue(ContractModel):
    value: str | int | None
    basis: Basis


class ProvenanceReference(ContractModel):
    workbook_name: str
    sheet_name: str
    row_number: int | None = None
    source_column: int | None = None
    source_column_letter: str | None = None
    source_cell: str | None = None
    source_header: str | None = None
    source_kind: Literal["row", "dataset", "workbook"] = "row"
    dataset_id: str | None = None
    dataset_type: str | None = None
    scope_code: str | None = None
    business_date: str | None = None
    version: int | None = None
    parser_version: str
    source_row_id: str
    field: str | None = None
    value: str | None = None
    note: str | None = None


class SourcePreviewRow(ContractModel):
    row_number: int
    values: list[Any]


class SourcePreviewResponse(ContractModel):
    workbook_name: str
    sheet_name: str
    target_cell: str
    target_row: int
    target_column: int
    target_value: Any
    columns: list[str]
    rows: list[SourcePreviewRow]
    header_row: int | None = None
    column_labels: list[Any] = Field(default_factory=list)
    import_id: str
    original_filename: str
    # Only set for multi-source (non-OSIP) rows, whose "import_id" above is
    # actually a DatasetVersion id, not an ImportBatch id - GET
    # /imports/{import_id}/source only knows ImportBatch rows, so the
    # frontend must download via /source-uploads/{source_upload_id}/source
    # instead whenever this is present.
    source_upload_id: str | None = None


class MetricInputProvenance(ContractModel):
    code: str
    label: str
    value: str | int | None
    basis: Basis
    source_refs: list[ProvenanceReference] = Field(default_factory=list)


class MetricProvenance(ContractModel):
    code: str
    label: str
    basis: Basis
    value: str | int | None
    formula: str | None = None
    explanation: str
    source_refs: list[ProvenanceReference] = Field(default_factory=list)
    inputs: list[MetricInputProvenance] = Field(default_factory=list)


class SnapshotProvenanceResponse(ContractModel):
    snapshot_id: str
    portfolio: str
    report_date: str
    version: int
    source_filename: str
    metrics: dict[str, MetricProvenance]


class ExcludedLot(ContractModel):
    security_code: str
    isin: str
    issuer: str
    purchase_amount_kzt: str
    missing_fields: list[str]


class SnapshotOverview(SnapshotSummary):
    data_label: Literal["operational/derived"]
    metrics: dict[str, MetricValue]
    # Lots excluded from derived_carrying_value_kzt/derived_operational_total_kzt
    # because they have no carrying amount (see snapshot_overview) - disclosed
    # here rather than left implicit, since those two metrics are now a real
    # partial total instead of turning "Unavailable" over one bad lot.
    excluded_lot_count: int
    excluded_purchase_value_kzt: str | None
    excluded_lots: list[ExcludedLot] = Field(default_factory=list)


class LotHolding(ContractModel):
    id: str
    source: SourceRef
    source_section: str
    security_code: str
    isin: str
    raw_security_type: str
    normalized_asset_class: str
    issuer: str
    valuation_method: str
    instrument_currency: str
    raw_sector: str
    rating_sp: str
    rating_moodys: str
    rating_fitch: str
    coupon_or_repo_rate: str | None
    nominal_value: str | None
    open_date: str | None
    close_date: str | None
    quantity: str
    purchase_date: str | None
    purchase_price: str | None
    purchase_yield: str | None
    current_ytm: str | None
    purchase_amount_native: str | None
    purchase_amount_kzt: str | None
    carrying_amount_native: str | None
    carrying_price_native: str | None
    reserve_kzt: str | None
    organizer_fee_kzt: str | None
    broker_fee_kzt: str | None
    report_fx_rate: str | None
    principal_indexation: str | None
    accrued_income_kzt: str | None
    previous_coupon_date: str | None
    next_coupon_date: str | None
    listing_rating: str | None
    derived_carrying_value_kzt: str | None
    unavailable_fields: list[str]


class InstrumentHolding(ContractModel):
    isin: str
    security_code: str
    issuer: str
    raw_security_type: str
    normalized_asset_class: str
    true_asset_class: str
    instrument_currency: str
    raw_sector: str
    lot_count: int
    quantity: str
    hpr_percent: str | None
    current_ytm: str | None
    carrying_amount_native: str | None
    rating_sp: str
    rating_moodys: str
    rating_fitch: str
    listing_rating: str
    purchase_amount_native: str
    purchase_amount_kzt: str
    # Both are null when one or more of this instrument's lots have no
    # source carrying amount (see _aggregated_holdings' derived_carrying_complete)
    # - never a fabricated zero, which would silently understate this
    # instrument's value and the portfolio's derived-basis total/weight.
    derived_carrying_value_kzt: str | None
    derived_carrying_incomplete: bool
    coupon_income_native_estimated: str
    coupon_income_kzt_estimated: str
    coupon_estimate_unavailable: bool
    source_refs: list[SourceRef]
    derived_weight_percent: str | None
    purchase_weight_percent: str


class LotHoldingsResponse(ContractModel):
    snapshot_id: str
    view: Literal["lots"]
    items: list[LotHolding]
    dividend_data_status: DividendDataStatus


class InstrumentHoldingsResponse(ContractModel):
    snapshot_id: str
    view: Literal["instruments"]
    value_basis: Literal["derived_carrying_value_kzt"]
    items: list[InstrumentHolding]
    dividend_data_status: DividendDataStatus


HoldingsResponse = Annotated[
    LotHoldingsResponse | InstrumentHoldingsResponse,
    Field(discriminator="view"),
]


class AllocationItem(ContractModel):
    label: str
    value_kzt: str
    weight_percent: str
    lot_count: int
    instrument_count: int


class AllocationResponse(ContractModel):
    snapshot_id: str
    dimension: Literal[
        "asset_class", "currency", "issuer", "valuation_method", "raw_sector", "rating"
    ]
    value_basis: Literal["derived_carrying_value_kzt", "purchase_amount_kzt"]
    total_value_kzt: str
    items: list[AllocationItem]
    # Lots whose derived carrying value is unavailable (see
    # _aggregated_holdings' derived_carrying_complete) are left out of
    # total_value_kzt/items entirely rather than folded in as zero;
    # excluded_value_kzt discloses their combined purchase value so a
    # reader can see the total is short by a known, named amount instead of
    # silently trusting an understated one. Null/0 when nothing was excluded.
    excluded_value_kzt: str | None
    excluded_lot_count: int


class CashBalance(ContractModel):
    id: str
    source: SourceRef
    raw_label: str
    currency: str
    custodian: str | None
    native_amount: str
    kzt_amount: str
    active: bool


class CashResponse(ContractModel):
    snapshot_id: str
    items: list[CashBalance]


class Settlement(ContractModel):
    id: str
    security_code: str
    isin: str
    raw_security_type: str
    issuer: str
    currency: str
    quantity: str
    settlement_date: str | None
    purchase_price: str | None
    amount_native: str | None
    amount_kzt: str | None
    source_refs: list[SourceRef]


class SettlementsResponse(ContractModel):
    snapshot_id: str
    raw_count: int
    deduplicated_count: int
    items: list[Settlement]


class IssueAcknowledgement(ContractModel):
    actor_id: str
    comment: str
    acknowledged_at: str


class DataQualityIssue(ContractModel):
    id: str
    code: str
    severity: Literal["blocker", "high", "medium", "low"]
    message: str
    affected_fields: list[str]
    source_refs: list[DQSourceRef]
    acknowledgement: IssueAcknowledgement | None
    owner_id: str | None
    due_date: str | None
    is_overdue: bool


class IssuesResponse(ContractModel):
    snapshot_id: str
    items: list[DataQualityIssue]


class CalendarEvent(ContractModel):
    id: str
    event_type: Literal[
        "settlement", "repo_open", "repo_close", "instrument_open", "maturity",
        "previous_coupon", "next_coupon"
    ]
    event_date: str
    status: Literal["historical", "upcoming", "overdue"]
    isin: str
    security_code: str
    title: str
    amount_native: str | None
    amount_kzt: str | None
    currency: str
    amount_basis: str
    source_refs: list[SourceRef]


class CalendarCounts(ContractModel):
    total: int
    upcoming: int
    overdue_settlements: int


class UnavailableSettlementTotal(ContractModel):
    value: None
    basis: Literal["unavailable"]
    reason: str


class CalendarResponse(ContractModel):
    snapshot_id: str
    report_date: str
    counts: CalendarCounts
    settlement_total: UnavailableSettlementTotal
    items: list[CalendarEvent]


class ReadinessSource(ContractModel):
    filename: str
    sha256: str
    parser_version: str


class ReadinessGates(ContractModel):
    independent_approval: bool
    critical_dq_acknowledged: bool
    published: bool
    source_first_mode: bool = False


class ExportReadiness(ContractModel):
    ready: bool
    label: str
    blocking_reasons: list[str]


class ReportReadinessResponse(ContractModel):
    snapshot_id: str
    import_id: str
    portfolio: str
    report_date: str
    version: int
    status: ImportState
    source: ReadinessSource
    gates: ReadinessGates
    critical_dq_count: int
    unacknowledged_critical_count: int
    operational_snapshot_export: ExportReadiness
    official_report_export: ExportReadiness


class ReportArtifact(ContractModel):
    id: str
    snapshot_id: str
    format: Literal["csv"]
    requested_by: str
    artifact_sha256: str
    disclosures: list[str]
    created_at: str
    artifact_url: str


class ReportListResponse(ContractModel):
    items: list[ReportArtifact]


class ReferenceDictionaryStatus(ContractModel):
    row_count: int
    updated_at: str | None


class ReferenceDictionaryUploadResponse(ContractModel):
    row_count: int
    previous_row_count: int
    added_isins: list[str]
    removed_isins: list[str]
    changed_isins: list[str]


class DividendDataStatus(ContractModel):
    freshness: Literal["fresh", "stale", "unknown", "missing"]
    source_filename: str | None
    source_sha256: str | None
    source_date: str | None
    uploaded_at: str | None
    latest_ex_date: str | None
    latest_pay_date: str | None
    future_pay_count: int
    row_count: int
    ticker_count: int
    stale_after_days: int


class DividendDataUploadResponse(DividendDataStatus):
    pass


class ActionItemCreateRequest(ContractModel):
    domain: str = Field(min_length=1, max_length=40)
    kind: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=500)
    dataset_type: str | None = Field(default=None, max_length=80)
    scope_code: str | None = Field(default=None, max_length=120)
    reference_key: str | None = Field(default=None, max_length=200)


class ActionItemAssignRequest(ContractModel):
    owner_id: str | None = Field(default=None, max_length=200)
    due_date: str | None = None
    reason: str = Field(min_length=1, max_length=4000)


class ActionItemResolveRequest(ContractModel):
    comment: str = Field(min_length=1, max_length=4000)


class ActionItemReopenRequest(ContractModel):
    reason: str = Field(min_length=1, max_length=4000)


class ActionItemResponse(ContractModel):
    id: str
    domain: str
    kind: str
    title: str
    dataset_type: str | None
    scope_code: str | None
    reference_key: str | None
    status: str
    owner_id: str | None
    due_date: str | None
    created_by: str
    created_at: str
    assigned_by: str | None
    assigned_at: str | None
    assignment_reason: str | None
    resolved_by: str | None
    resolved_at: str | None
    resolution_comment: str | None
    is_overdue: bool


class ActionItemListResponse(ContractModel):
    items: list[ActionItemResponse]


class DemoLoginRequest(ContractModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class DemoActorInfo(ContractModel):
    actor_id: str
    username: str
    display_name: str
    roles: list[str]
    domains: list[str]
    portfolios: list[str]


class DemoLoginResponse(ContractModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    actor: DemoActorInfo
