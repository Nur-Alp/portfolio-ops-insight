"""Allow a withdrawn workbook assignment to be imported again.

Revision ID: 0003_reupload_withdrawn
Revises: 0002_scoped_source_hash

Kept to 32 characters: PostgreSQL's default alembic_version.version_num
column is VARCHAR(32) and silently truncates on SQLite but errors on
PostgreSQL, so every revision id here must stay at or under that length.
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_reupload_withdrawn"
down_revision = "0002_scoped_source_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("import_batches", recreate="always") as batch:
            batch.drop_constraint("uq_import_source_portfolio", type_="unique")
    else:
        op.drop_constraint(
            "uq_import_source_portfolio", "import_batches", type_="unique"
        )
    op.create_index(
        "uq_active_import_source_portfolio",
        "import_batches",
        ["source_sha256", "portfolio_code"],
        unique=True,
        postgresql_where=sa.text("status != 'withdrawn'"),
        sqlite_where=sa.text("status != 'withdrawn'"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_import_source_portfolio", table_name="import_batches")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("import_batches", recreate="always") as batch:
            batch.create_unique_constraint(
                "uq_import_source_portfolio", ["source_sha256", "portfolio_code"]
            )
    else:
        op.create_unique_constraint(
            "uq_import_source_portfolio",
            "import_batches",
            ["source_sha256", "portfolio_code"],
        )
