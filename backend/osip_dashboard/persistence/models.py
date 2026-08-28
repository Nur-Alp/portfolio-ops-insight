"""SQLAlchemy models for versioned imports and immutable portfolio snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from osip_dashboard.persistence import Base


MONEY = Numeric(38, 12)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImportStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    VALIDATED = "validated"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


status_type = Enum(
    ImportStatus,
    values_callable=lambda values: [value.value for value in values],
    native_enum=False,
    length=24,
)


class Portfolio(Base):
    __tablename__ = "portfolios"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KZT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceUpload(Base):
    """One immutable physical source file, shared by independently governed datasets."""

    __tablename__ = "source_uploads"
    __table_args__ = (
        UniqueConstraint(
            "source_sha256", "uploader_id", name="uq_source_upload_hash_uploader"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    detected_source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    detection: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    uploader_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    datasets: Mapped[list["DatasetVersion"]] = relationship(
        back_populates="source_upload", cascade="all, delete-orphan"
    )


class DatasetVersion(Base):
    """A logical dataset parsed from a source upload and published independently."""

    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint(
            "dataset_type", "scope_code", "business_date", "version",
            name="uq_dataset_scope_date_version",
        ),
        Index("ix_dataset_scope_date", "dataset_type", "scope_code", "business_date"),
        Index("ix_dataset_status", "status"),
        # Scoped by uploader_id, not just dataset_type/scope_code/business_date:
        # per-uploader visibility (_has_uploader_access in routes/multi_source.py)
        # means two operators can each have their own published version for the
        # same business date. Without uploader_id here, one operator's publish
        # would collide with (and get superseded by) a completely different
        # operator's publish for the same date - an operator whose data they
        # cannot even see, per the visibility rule.
        Index(
            "uq_published_dataset_scope_date",
            "dataset_type", "scope_code", "business_date", "uploader_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
            sqlite_where=text("status = 'published'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_upload_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_uploads.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    dataset_type: Mapped[str] = mapped_column(String(80), nullable=False)
    detected_key: Mapped[str] = mapped_column(String(120), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_code: Mapped[str] = mapped_column(String(120), nullable=False)
    source_report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ImportStatus] = mapped_column(status_type, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    uploader_id: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    publisher_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_upload: Mapped[SourceUpload] = relationship(back_populates="datasets")
    records: Mapped[list["DatasetRecord"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    issues: Mapped[list["DatasetIssue"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["DatasetAuditEvent"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetRecord(Base):
    __tablename__ = "dataset_records"
    __table_args__ = (
        UniqueConstraint("dataset_id", "record_type", "record_key", name="uq_dataset_record"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    record_type: Mapped[str] = mapped_column(String(80), nullable=False)
    record_key: Mapped[str] = mapped_column(String(300), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_ref: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    formulas: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    cached_values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    dataset: Mapped[DatasetVersion] = relationship(back_populates="records")


class DatasetIssue(Base):
    __tablename__ = "dataset_issues"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    affected_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    acknowledged_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acknowledgement_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped[DatasetVersion] = relationship(back_populates="issues")


class DatasetAuditEvent(Base):
    __tablename__ = "dataset_audit_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset: Mapped[DatasetVersion] = relationship(back_populates="audit_events")


class ClientIdentityResolution(Base):
    """Manual decision for a client/open-date match; source evidence is untouched."""

    __tablename__ = "client_identity_resolutions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "record_id", name="uq_client_identity_resolution"),
        Index("ix_client_identity_resolution_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False, index=True)
    record_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_records.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    resolved_account: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_by: Mapped[str] = mapped_column(String(200), nullable=False)
    resolution_comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset: Mapped[DatasetVersion] = relationship()
    record: Mapped[DatasetRecord] = relationship()


class ActionItem(Base):
    """An operational to-do (a risk breach exception, an accounting close
    step, ...) - deliberately not a data-quality finding.

    A DQ issue says the *data* is wrong; an action item says the data is
    right and a person needs to do something about what it shows. Kept
    separate from both DatasetIssue (multi-source) and DataQualityIssueRecord
    (legacy OSIP) rather than extending either, since neither read that
    distinction and both would need real changes to carry this.

    Referenced loosely (dataset_type/scope_code/reference_key), not by a
    foreign key to a DatasetVersion/DatasetRecord row: those rows are
    replaced on every republish, but a breach or a close step is about the
    same real-world thing (an issuer's limit line, a reporting period)
    across many republishes. reference_key is expected to be a dataset's
    own stable identity, e.g. the record_key already computed for risk
    limit lines.
    """

    __tablename__ = "action_items"
    __table_args__ = (
        Index("ix_action_item_domain_status", "domain", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    # Reuses the same domain vocabulary as require_domain/_dataset_domain
    # ("risk", "accounting", "client_ops", ...) for access control, rather
    # than inventing a parallel scoping concept.
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    dataset_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scope_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reference_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    owner_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    assigned_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assignment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    rule_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    scope_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dataset_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    actual_values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    difference: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    tolerance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InstrumentRecord(Base):
    __tablename__ = "instruments"

    isin: Mapped[str] = mapped_column(String(32), primary_key=True)
    security_code: Mapped[str] = mapped_column(String(120), nullable=False)
    issuer: Mapped[str] = mapped_column(String(300), nullable=False)
    raw_security_type: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_asset_class: Mapped[str] = mapped_column(String(80), nullable=False)
    instrument_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    raw_sector: Mapped[str] = mapped_column(String(500), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    basis: Mapped[str] = mapped_column(String(20), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False)
    unavailable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        Index(
            "uq_active_import_source_portfolio",
            "source_sha256",
            "portfolio_code",
            unique=True,
            postgresql_where=text("status NOT IN ('withdrawn', 'rejected', 'failed')"),
            sqlite_where=text("status NOT IN ('withdrawn', 'rejected', 'failed')"),
        ),
        UniqueConstraint("portfolio_code", "report_date", "version", name="uq_import_version"),
        Index("ix_import_portfolio_date", "portfolio_code", "report_date"),
        Index("ix_import_status", "status"),
        Index(
            "uq_published_import_per_portfolio_date",
            "portfolio_code",
            "report_date",
            unique=True,
            postgresql_where=text("status = 'published'"),
            sqlite_where=text("status = 'published'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_upload_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_uploads.id", ondelete="RESTRICT", name="fk_import_source_upload"), nullable=True, index=True
    )
    dataset_type: Mapped[str] = mapped_column(String(80), nullable=False, default="portfolio_snapshot")
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False, default="portfolio")
    scope_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    portfolio_code: Mapped[str | None] = mapped_column(
        ForeignKey("portfolios.code", ondelete="RESTRICT"), nullable=True
    )
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    # OSIP field -> zero-based column index, resolved by header label at parse
    # time (see ingestion/osip_workbook.py's _resolve_columns). Only set for
    # osip_portfolio imports; lets provenance lookups point at the exact
    # physical cell for THIS import's own layout instead of assuming every
    # import shares one fixed column map (it doesn't - see the 2026-08
    # column-layout change this field exists to survive). Null for imports
    # predating this field and for non-OSIP dataset types.
    osip_resolved_columns: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ImportStatus] = mapped_column(status_type, nullable=False, default=ImportStatus.DRAFT)
    uploader_id: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    publisher_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    portfolio: Mapped[Portfolio | None] = relationship()
    source_upload: Mapped[SourceUpload | None] = relationship()
    snapshot: Mapped["PortfolioSnapshotRecord | None"] = relationship(
        back_populates="import_batch", uselist=False, cascade="all, delete-orphan"
    )
    source_rows: Mapped[list["SourceRow"]] = relationship(
        back_populates="import_batch", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="import_batch", cascade="all, delete-orphan"
    )


class PortfolioSnapshotRecord(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("import_id", name="uq_snapshot_import"),
        UniqueConstraint("portfolio_code", "report_date", "version", name="uq_snapshot_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="RESTRICT"), nullable=False
    )
    portfolio_code: Mapped[str] = mapped_column(
        ForeignKey("portfolios.code", ondelete="RESTRICT"), nullable=False
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    value_label: Mapped[str] = mapped_column(
        String(80), nullable=False, default="Derived carrying value"
    )
    position_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_isin_count: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_settlement_count: Mapped[int] = mapped_column(Integer, nullable=False)
    settlement_count: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_amount_kzt: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    derived_carrying_value_kzt: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cash_kzt: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    derived_operational_total_kzt: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_fees_kzt: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_reserves_kzt: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="snapshot")
    position_lots: Mapped[list["PositionLotRecord"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    cash_balances: Mapped[list["CashBalanceRecord"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    settlements: Mapped[list["SettlementEventRecord"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    issues: Mapped[list["DataQualityIssueRecord"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class SourceRow(Base):
    __tablename__ = "source_rows"
    __table_args__ = (
        UniqueConstraint("import_id", "sheet_name", "row_number", name="uq_import_source_row"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="RESTRICT"), nullable=False
    )
    workbook_name: Mapped[str] = mapped_column(String(500), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(120), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_values: Mapped[list[Any]] = mapped_column(JSON, nullable=False)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="source_rows")


class PositionLotRecord(Base):
    __tablename__ = "position_lots"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_row_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_rows.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    source_section: Mapped[str] = mapped_column(String(240), nullable=False)
    security_code: Mapped[str] = mapped_column(String(120), nullable=False)
    isin: Mapped[str] = mapped_column(
        ForeignKey("instruments.isin", ondelete="RESTRICT"), nullable=False, index=True
    )
    raw_security_type: Mapped[str] = mapped_column(String(120), nullable=False)
    issuer: Mapped[str] = mapped_column(String(300), nullable=False)
    valuation_method: Mapped[str] = mapped_column(String(300), nullable=False)
    instrument_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    raw_sector: Mapped[str] = mapped_column(String(500), nullable=False)
    rating_sp: Mapped[str] = mapped_column(String(40), nullable=False)
    rating_moodys: Mapped[str] = mapped_column(String(40), nullable=False)
    rating_fitch: Mapped[str] = mapped_column(String(40), nullable=False)
    coupon_or_repo_rate: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    nominal_value: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    open_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    purchase_yield: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    current_ytm: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    purchase_amount_native: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    purchase_amount_kzt: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    carrying_amount_native: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    carrying_price_native: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    reserve_kzt: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    organizer_fee_kzt: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    broker_fee_kzt: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    accrued_income_kzt: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    principal_indexation: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    report_fx_rate: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    previous_coupon_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_coupon_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    listing_rating: Mapped[str] = mapped_column(String(120), nullable=False)
    derived_carrying_value_kzt: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    expected_coupon_cached: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    coupon_period_days: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    coupon_indexation: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    unavailable_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    snapshot: Mapped[PortfolioSnapshotRecord] = relationship(back_populates="position_lots")
    source_row: Mapped[SourceRow] = relationship()
    instrument: Mapped[InstrumentRecord] = relationship()


class CashBalanceRecord(Base):
    __tablename__ = "cash_balances"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_row_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_rows.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    raw_label: Mapped[str] = mapped_column(String(500), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    custodian: Mapped[str | None] = mapped_column(String(300), nullable=True)
    native_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    kzt_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    snapshot: Mapped[PortfolioSnapshotRecord] = relationship(back_populates="cash_balances")
    source_row: Mapped[SourceRow] = relationship()


class SettlementEventRecord(Base):
    __tablename__ = "settlement_events"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "signature_hash", name="uq_snapshot_settlement_signature"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    security_code: Mapped[str] = mapped_column(String(120), nullable=False)
    isin: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_security_type: Mapped[str] = mapped_column(String(120), nullable=False)
    issuer: Mapped[str] = mapped_column(String(300), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    amount_native: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    amount_kzt: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    snapshot: Mapped[PortfolioSnapshotRecord] = relationship(back_populates="settlements")
    source_links: Mapped[list["SettlementSourceLink"]] = relationship(
        back_populates="settlement", cascade="all, delete-orphan"
    )


class SettlementSourceLink(Base):
    __tablename__ = "settlement_source_links"

    settlement_id: Mapped[UUID] = mapped_column(
        ForeignKey("settlement_events.id", ondelete="RESTRICT"), primary_key=True
    )
    source_row_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_rows.id", ondelete="RESTRICT"), primary_key=True
    )

    settlement: Mapped[SettlementEventRecord] = relationship(back_populates="source_links")
    source_row: Mapped[SourceRow] = relationship()


class DataQualityIssueRecord(Base):
    __tablename__ = "data_quality_issues"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    affected_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    owner_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    snapshot: Mapped[PortfolioSnapshotRecord] = relationship(back_populates="issues")
    acknowledgement: Mapped["DataQualityAcknowledgement | None"] = relationship(
        back_populates="issue", uselist=False, cascade="all, delete-orphan"
    )


class DataQualityAcknowledgement(Base):
    __tablename__ = "data_quality_acknowledgements"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    issue_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_quality_issues.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    issue: Mapped[DataQualityIssueRecord] = relationship(back_populates="acknowledgement")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    import_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    import_batch: Mapped[ImportBatch | None] = relationship(back_populates="audit_events")


class ReportRun(Base):
    __tablename__ = "report_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requested_by: Mapped[str] = mapped_column(String(200), nullable=False)
    format: Mapped[str] = mapped_column(String(12), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    disclosures: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    snapshot: Mapped[PortfolioSnapshotRecord] = relationship()


class DemoAccount(Base):
    """A fixed demo-persona login for the self-issued 'demo' identity provider.

    Not a general user-account system: this exists only to gate a shared
    demo deployment behind real credentials instead of spoofable dev
    headers. ``roles``/``domains``/``portfolios`` are stored as comma-lists
    and parsed the same way ``DevelopmentHeaderIdentityProvider`` parses its
    headers, so a seeded account maps directly onto an ``Actor``.
    """

    __tablename__ = "demo_accounts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    roles: Mapped[str] = mapped_column(String(200), nullable=False)
    domains: Mapped[str] = mapped_column(String(200), nullable=False)
    portfolios: Mapped[str] = mapped_column(String(200), nullable=False, default="*")
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
