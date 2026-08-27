"""Store audited manual client identity/open-date resolutions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_client_identity_resolutions"
down_revision = "0007_multi_source_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_identity_resolutions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="confirmed"),
        sa.Column("resolved_account", sa.String(200), nullable=True),
        sa.Column("resolved_by", sa.String(200), nullable=False),
        sa.Column("resolution_comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["dataset_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["record_id"], ["dataset_records.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("dataset_id", "record_id", name="uq_client_identity_resolution"),
    )
    op.create_index("ix_client_identity_resolutions_dataset_id", "client_identity_resolutions", ["dataset_id"])
    op.create_index("ix_client_identity_resolutions_record_id", "client_identity_resolutions", ["record_id"])
    op.create_index("ix_client_identity_resolution_status", "client_identity_resolutions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_client_identity_resolution_status", table_name="client_identity_resolutions")
    op.drop_index("ix_client_identity_resolutions_record_id", table_name="client_identity_resolutions")
    op.drop_index("ix_client_identity_resolutions_dataset_id", table_name="client_identity_resolutions")
    op.drop_table("client_identity_resolutions")
