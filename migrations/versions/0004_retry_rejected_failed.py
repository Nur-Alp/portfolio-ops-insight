"""Allow re-uploading a rejected or failed workbook without withdrawing it.

Revision ID: 0004_retry_rejected_failed
Revises: 0003_reupload_withdrawn

Kept to 32 characters: PostgreSQL's default alembic_version.version_num
column is VARCHAR(32) and silently truncates on SQLite but errors on
PostgreSQL, so every revision id here must stay at or under that length.
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_retry_rejected_failed"
down_revision = "0003_reupload_withdrawn"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_active_import_source_portfolio", table_name="import_batches")
    op.create_index(
        "uq_active_import_source_portfolio",
        "import_batches",
        ["source_sha256", "portfolio_code"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('withdrawn', 'rejected', 'failed')"),
        sqlite_where=sa.text("status NOT IN ('withdrawn', 'rejected', 'failed')"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_import_source_portfolio", table_name="import_batches")
    op.create_index(
        "uq_active_import_source_portfolio",
        "import_batches",
        ["source_sha256", "portfolio_code"],
        unique=True,
        postgresql_where=sa.text("status != 'withdrawn'"),
        sqlite_where=sa.text("status != 'withdrawn'"),
    )
