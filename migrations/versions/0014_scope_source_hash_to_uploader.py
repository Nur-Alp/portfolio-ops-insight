"""Allow identical source bytes to be re-uploaded by another operator.

The blob remains content-addressed by SHA-256, while each uploader receives a
separate immutable source-upload ownership record and dataset version chain.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0014_scope_source_hash_to_uploader"
down_revision = "0013_backfill_formula_carrying_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        inspector = sa.inspect(bind)
        for constraint in inspector.get_unique_constraints("source_uploads"):
            if constraint.get("column_names") == ["source_sha256"] and constraint.get("name"):
                op.drop_constraint(constraint["name"], "source_uploads", type_="unique")
        op.create_unique_constraint(
            "uq_source_upload_hash_uploader",
            "source_uploads",
            ["source_sha256", "uploader_id"],
        )
        return

    # SQLite represents the original unique=True column constraint as an
    # unnamed auto-index, so Alembic cannot drop it by name. Recreate the
    # small source-upload table with the scoped constraint while preserving
    # all immutable rows and their primary keys.
    metadata = sa.MetaData()
    source_uploads = sa.Table(
        "source_uploads",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("file_format", sa.String(20), nullable=False),
        sa.Column("detected_source_type", sa.String(80), nullable=False),
        sa.Column("detection", sa.JSON(), nullable=False),
        sa.Column("uploader_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_sha256", "uploader_id", name="uq_source_upload_hash_uploader"
        ),
    )
    with op.batch_alter_table(
        "source_uploads", recreate="always", copy_from=source_uploads
    ):
        pass


def downgrade() -> None:
    # A downgrade cannot safely collapse two uploader-owned records that share
    # one SHA-256 without choosing which audit owner survives. Leave the
    # widened ownership model in place rather than deleting evidence.
    pass
