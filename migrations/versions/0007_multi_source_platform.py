"""Add physical source uploads and independently governed dataset versions."""

from __future__ import annotations

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0007_multi_source_platform"
down_revision = "0006_current_ytm"
branch_labels = None
depends_on = None


status_type = sa.Enum(
    "draft", "validating", "validated", "approved", "published", "failed",
    "rejected", "superseded", "withdrawn", name="importstatus", native_enum=False,
    length=24,
)
money = sa.Numeric(38, 12)


def upgrade() -> None:
    op.create_table(
        "source_uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("file_format", sa.String(20), nullable=False),
        sa.Column("detected_source_type", sa.String(80), nullable=False),
        sa.Column("detection", sa.JSON(), nullable=False),
        sa.Column("uploader_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("import_batches") as batch:
        batch.add_column(sa.Column("source_upload_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("dataset_type", sa.String(80), nullable=False, server_default="portfolio_snapshot"))
        batch.add_column(sa.Column("scope_type", sa.String(40), nullable=False, server_default="portfolio"))
        batch.add_column(sa.Column("scope_code", sa.String(120), nullable=True))
        batch.add_column(sa.Column("source_report_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("business_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_import_source_upload", "source_uploads", ["source_upload_id"], ["id"], ondelete="RESTRICT")
        batch.create_index("ix_import_batches_source_upload_id", ["source_upload_id"])

    bind = op.get_bind()
    metadata = sa.MetaData()
    imports = sa.Table("import_batches", metadata, autoload_with=bind)
    uploads = sa.Table("source_uploads", metadata, autoload_with=bind)
    by_hash: dict[str, object] = {}
    for row in bind.execute(sa.select(imports)).mappings():
        upload_id = by_hash.get(row["source_sha256"])
        if upload_id is None:
            generated_uuid = uuid4()
            # Reflected SQLite UUID columns do not retain SQLAlchemy's UUID bind
            # processor during an in-place Alembic upgrade.
            upload_id = generated_uuid.hex if bind.dialect.name == "sqlite" else generated_uuid
            by_hash[row["source_sha256"]] = upload_id
            bind.execute(
                uploads.insert().values(
                    id=upload_id,
                    source_sha256=row["source_sha256"],
                    original_filename=row["original_filename"],
                    storage_key=row["storage_key"],
                    file_format="xls",
                    detected_source_type="osip_portfolio",
                    detection={"backfilled": True, "datasets": [{"key": "portfolio", "dataset_type": "portfolio_snapshot"}]},
                    uploader_id=row["uploader_id"],
                    created_at=row["created_at"],
                )
            )
        bind.execute(
            imports.update().where(imports.c.id == row["id"]).values(
                source_upload_id=upload_id,
                dataset_type="portfolio_snapshot",
                scope_type="portfolio",
                scope_code=row["portfolio_code"],
                source_report_date=row["report_date"],
                business_date=row["report_date"],
                generated_at=row["created_at"],
            )
        )

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_upload_id", sa.Uuid(), sa.ForeignKey("source_uploads.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dataset_type", sa.String(80), nullable=False),
        sa.Column("detected_key", sa.String(120), nullable=False),
        sa.Column("scope_type", sa.String(40), nullable=False),
        sa.Column("scope_code", sa.String(120), nullable=False),
        sa.Column("source_report_date", sa.Date(), nullable=True),
        sa.Column("business_date", sa.Date(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parser_version", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", status_type, nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("uploader_id", sa.String(200), nullable=False),
        sa.Column("reviewer_id", sa.String(200), nullable=True),
        sa.Column("publisher_id", sa.String(200), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("dataset_type", "scope_code", "business_date", "version", name="uq_dataset_scope_date_version"),
    )
    op.create_index("ix_dataset_versions_source_upload_id", "dataset_versions", ["source_upload_id"])
    op.create_index("ix_dataset_scope_date", "dataset_versions", ["dataset_type", "scope_code", "business_date"])
    op.create_index("ix_dataset_status", "dataset_versions", ["status"])
    op.create_index(
        "uq_published_dataset_scope_date", "dataset_versions",
        ["dataset_type", "scope_code", "business_date"], unique=True,
        postgresql_where=sa.text("status = 'published'"), sqlite_where=sa.text("status = 'published'"),
    )
    op.create_table(
        "dataset_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("record_type", sa.String(80), nullable=False),
        sa.Column("record_key", sa.String(300), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source_ref", sa.JSON(), nullable=False),
        sa.Column("raw_values", sa.JSON(), nullable=False),
        sa.Column("formulas", sa.JSON(), nullable=False),
        sa.Column("cached_values", sa.JSON(), nullable=False),
        sa.UniqueConstraint("dataset_id", "record_type", "record_key", name="uq_dataset_record"),
    )
    op.create_index("ix_dataset_records_dataset_id", "dataset_records", ["dataset_id"])
    op.create_table(
        "dataset_issues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("affected_fields", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("acknowledged_by", sa.String(200), nullable=True),
        sa.Column("acknowledgement_comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_dataset_issues_dataset_id", "dataset_issues", ["dataset_id"])
    op.create_index("ix_dataset_issues_code", "dataset_issues", ["code"])
    op.create_table(
        "dataset_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dataset_audit_events_dataset_id", "dataset_audit_events", ["dataset_id"])
    op.create_table(
        "reconciliation_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rule_code", sa.String(80), nullable=False),
        sa.Column("scope_code", sa.String(120), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=True),
        sa.Column("dataset_ids", sa.JSON(), nullable=False),
        sa.Column("actual_values", sa.JSON(), nullable=False),
        sa.Column("difference", money, nullable=True),
        sa.Column("tolerance", money, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reconciliation_results_rule_code", "reconciliation_results", ["rule_code"])
    op.create_index("ix_reconciliation_results_scope_code", "reconciliation_results", ["scope_code"])


def downgrade() -> None:
    op.drop_table("reconciliation_results")
    op.drop_table("dataset_audit_events")
    op.drop_table("dataset_issues")
    op.drop_table("dataset_records")
    op.drop_table("dataset_versions")
    with op.batch_alter_table("import_batches") as batch:
        batch.drop_index("ix_import_batches_source_upload_id")
        batch.drop_constraint("fk_import_source_upload", type_="foreignkey")
        for column in ("generated_at", "business_date", "source_report_date", "scope_code", "scope_type", "dataset_type", "source_upload_id"):
            batch.drop_column(column)
    op.drop_table("source_uploads")
