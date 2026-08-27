"""Initial versioned OSIP import schema.

Revision ID: 0001_versioned_imports
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_versioned_imports"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("code", sa.String(16), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("reporting_currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "portfolio_code",
            sa.String(16),
            sa.ForeignKey("portfolios.code", ondelete="RESTRICT"),
        ),
        sa.Column("report_date", sa.Date()),
        sa.Column("version", sa.Integer()),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("parser_version", sa.String(40), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "validating",
                "validated",
                "approved",
                "published",
                "failed",
                "rejected",
                "superseded",
                name="importstatus",
                native_enum=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("uploader_id", sa.String(200), nullable=False),
        sa.Column("reviewer_id", sa.String(200)),
        sa.Column("publisher_id", sa.String(200)),
        sa.Column("review_comment", sa.Text()),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source_sha256", name="uq_import_source_sha256"),
        sa.UniqueConstraint(
            "portfolio_code", "report_date", "version", name="uq_import_version"
        ),
    )
    op.create_index(
        "ix_import_portfolio_date",
        "import_batches",
        ["portfolio_code", "report_date"],
    )
    op.create_index("ix_import_status", "import_batches", ["status"])
    op.create_index(
        "uq_published_import_per_portfolio_date",
        "import_batches",
        ["portfolio_code", "report_date"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
        sqlite_where=sa.text("status = 'published'"),
    )
    op.create_table(
        "instruments",
        sa.Column("isin", sa.String(32), primary_key=True),
        sa.Column("security_code", sa.String(120), nullable=False),
        sa.Column("issuer", sa.String(300), nullable=False),
        sa.Column("raw_security_type", sa.String(120), nullable=False),
        sa.Column("normalized_asset_class", sa.String(80), nullable=False),
        sa.Column("instrument_currency", sa.String(3), nullable=False),
        sa.Column("raw_sector", sa.String(500), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "metric_definitions",
        sa.Column("code", sa.String(80), primary_key=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("basis", sa.String(20), nullable=False),
        sa.Column("unit", sa.String(20)),
        sa.Column("formula", sa.Text()),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("unavailable_reason", sa.Text()),
    )
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "import_id",
            sa.Uuid(),
            sa.ForeignKey("import_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "portfolio_code",
            sa.String(16),
            sa.ForeignKey("portfolios.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("value_label", sa.String(80), nullable=False),
        sa.Column("position_count", sa.Integer(), nullable=False),
        sa.Column("unique_isin_count", sa.Integer(), nullable=False),
        sa.Column("raw_settlement_count", sa.Integer(), nullable=False),
        sa.Column("settlement_count", sa.Integer(), nullable=False),
        sa.Column("purchase_amount_kzt", sa.Numeric(38, 12), nullable=False),
        sa.Column("derived_carrying_value_kzt", sa.Numeric(38, 12), nullable=False),
        sa.Column("cash_kzt", sa.Numeric(38, 12), nullable=False),
        sa.Column("derived_operational_total_kzt", sa.Numeric(38, 12), nullable=False),
        sa.Column("total_fees_kzt", sa.Numeric(38, 12), nullable=False),
        sa.Column("total_reserves_kzt", sa.Numeric(38, 12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("import_id", name="uq_snapshot_import"),
        sa.UniqueConstraint(
            "portfolio_code", "report_date", "version", name="uq_snapshot_version"
        ),
    )
    op.create_table(
        "source_rows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "import_id",
            sa.Uuid(),
            sa.ForeignKey("import_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("workbook_name", sa.String(500), nullable=False),
        sa.Column("sheet_name", sa.String(120), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("row_kind", sa.String(30), nullable=False),
        sa.Column("parser_version", sa.String(40), nullable=False),
        sa.Column("raw_values", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "import_id", "sheet_name", "row_number", name="uq_import_source_row"
        ),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "import_id",
            sa.Uuid(),
            sa.ForeignKey("import_batches.id", ondelete="RESTRICT"),
        ),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_import_id", "audit_events", ["import_id"])
    op.create_table(
        "position_lots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_row_id",
            sa.Uuid(),
            sa.ForeignKey("source_rows.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("source_section", sa.String(240), nullable=False),
        sa.Column("security_code", sa.String(120), nullable=False),
        sa.Column("isin", sa.String(32), nullable=False),
        sa.Column("raw_security_type", sa.String(120), nullable=False),
        sa.Column("issuer", sa.String(300), nullable=False),
        sa.Column("valuation_method", sa.String(300), nullable=False),
        sa.Column("instrument_currency", sa.String(3), nullable=False),
        sa.Column("raw_sector", sa.String(500), nullable=False),
        sa.Column("rating_sp", sa.String(40), nullable=False),
        sa.Column("rating_moodys", sa.String(40), nullable=False),
        sa.Column("rating_fitch", sa.String(40), nullable=False),
        sa.Column("coupon_or_repo_rate", sa.Numeric(38, 12)),
        sa.Column("nominal_value", sa.Numeric(38, 12)),
        sa.Column("open_date", sa.Date()),
        sa.Column("close_date", sa.Date()),
        sa.Column("quantity", sa.Numeric(38, 12), nullable=False),
        sa.Column("purchase_date", sa.Date()),
        sa.Column("purchase_price", sa.Numeric(38, 12)),
        sa.Column("purchase_yield", sa.Numeric(38, 12)),
        sa.Column("purchase_amount_native", sa.Numeric(38, 12)),
        sa.Column("purchase_amount_kzt", sa.Numeric(38, 12)),
        sa.Column("carrying_amount_native", sa.Numeric(38, 12)),
        sa.Column("reserve_kzt", sa.Numeric(38, 12)),
        sa.Column("organizer_fee_kzt", sa.Numeric(38, 12)),
        sa.Column("broker_fee_kzt", sa.Numeric(38, 12)),
        sa.Column("accrued_income_kzt", sa.Numeric(38, 12)),
        sa.Column("principal_indexation", sa.Numeric(38, 12)),
        sa.Column("report_fx_rate", sa.Numeric(38, 12)),
        sa.Column("previous_coupon_date", sa.Date()),
        sa.Column("next_coupon_date", sa.Date()),
        sa.Column("listing_rating", sa.String(120), nullable=False),
        sa.Column("derived_carrying_value_kzt", sa.Numeric(38, 12)),
        sa.Column("unavailable_fields", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["isin"], ["instruments.isin"], ondelete="RESTRICT"),
    )
    op.create_index("ix_position_lots_snapshot_id", "position_lots", ["snapshot_id"])
    op.create_index("ix_position_lots_isin", "position_lots", ["isin"])
    op.create_table(
        "cash_balances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_row_id",
            sa.Uuid(),
            sa.ForeignKey("source_rows.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("raw_label", sa.String(500), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("custodian", sa.String(300)),
        sa.Column("native_amount", sa.Numeric(38, 12), nullable=False),
        sa.Column("kzt_amount", sa.Numeric(38, 12), nullable=False),
    )
    op.create_index("ix_cash_balances_snapshot_id", "cash_balances", ["snapshot_id"])
    op.create_table(
        "settlement_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("signature_hash", sa.String(64), nullable=False),
        sa.Column("security_code", sa.String(120), nullable=False),
        sa.Column("isin", sa.String(32), nullable=False),
        sa.Column("raw_security_type", sa.String(120), nullable=False),
        sa.Column("issuer", sa.String(300), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 12), nullable=False),
        sa.Column("settlement_date", sa.Date()),
        sa.Column("purchase_price", sa.Numeric(38, 12)),
        sa.Column("amount_native", sa.Numeric(38, 12)),
        sa.Column("amount_kzt", sa.Numeric(38, 12)),
        sa.UniqueConstraint(
            "snapshot_id", "signature_hash", name="uq_snapshot_settlement_signature"
        ),
    )
    op.create_index("ix_settlement_events_snapshot_id", "settlement_events", ["snapshot_id"])
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("affected_fields", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
    )
    op.create_index("ix_data_quality_issues_snapshot_id", "data_quality_issues", ["snapshot_id"])
    op.create_index("ix_data_quality_issues_code", "data_quality_issues", ["code"])
    op.create_table(
        "settlement_source_links",
        sa.Column(
            "settlement_id",
            sa.Uuid(),
            sa.ForeignKey("settlement_events.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "source_row_id",
            sa.Uuid(),
            sa.ForeignKey("source_rows.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )
    op.create_table(
        "data_quality_acknowledgements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "issue_id",
            sa.Uuid(),
            sa.ForeignKey("data_quality_issues.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "report_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("format", sa.String(12), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("disclosures", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_report_runs_snapshot_id", "report_runs", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_report_runs_snapshot_id", table_name="report_runs")
    op.drop_table("report_runs")
    op.drop_table("data_quality_acknowledgements")
    op.drop_table("settlement_source_links")
    op.drop_index("ix_data_quality_issues_code", table_name="data_quality_issues")
    op.drop_index("ix_data_quality_issues_snapshot_id", table_name="data_quality_issues")
    op.drop_table("data_quality_issues")
    op.drop_index("ix_settlement_events_snapshot_id", table_name="settlement_events")
    op.drop_table("settlement_events")
    op.drop_index("ix_cash_balances_snapshot_id", table_name="cash_balances")
    op.drop_table("cash_balances")
    op.drop_index("ix_position_lots_isin", table_name="position_lots")
    op.drop_index("ix_position_lots_snapshot_id", table_name="position_lots")
    op.drop_table("position_lots")
    op.drop_index("ix_audit_events_import_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("source_rows")
    op.drop_table("portfolio_snapshots")
    op.drop_index(
        "uq_published_import_per_portfolio_date", table_name="import_batches"
    )
    op.drop_index("ix_import_status", table_name="import_batches")
    op.drop_index("ix_import_portfolio_date", table_name="import_batches")
    op.drop_table("import_batches")
    op.drop_table("metric_definitions")
    op.drop_table("instruments")
    op.drop_table("portfolios")
