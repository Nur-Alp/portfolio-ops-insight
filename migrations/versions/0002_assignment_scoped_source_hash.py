"""Scope source idempotency to a portfolio assignment.

Revision ID: 0002_scoped_source_hash
Revises: 0001_versioned_imports

Kept to 32 characters: PostgreSQL's default alembic_version.version_num
column is VARCHAR(32) and silently truncates on SQLite but errors on
PostgreSQL, so every revision id here must stay at or under that length.
"""

from alembic import op


revision = "0002_scoped_source_hash"
down_revision = "0001_versioned_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("import_batches", recreate="always") as batch:
            batch.drop_constraint("uq_import_source_sha256", type_="unique")
            batch.create_unique_constraint(
                "uq_import_source_portfolio", ["source_sha256", "portfolio_code"]
            )
    else:
        op.drop_constraint(
            "uq_import_source_sha256", "import_batches", type_="unique"
        )
        op.create_unique_constraint(
            "uq_import_source_portfolio",
            "import_batches",
            ["source_sha256", "portfolio_code"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("import_batches", recreate="always") as batch:
            batch.drop_constraint("uq_import_source_portfolio", type_="unique")
            batch.create_unique_constraint("uq_import_source_sha256", ["source_sha256"])
    else:
        op.drop_constraint(
            "uq_import_source_portfolio", "import_batches", type_="unique"
        )
        op.create_unique_constraint(
            "uq_import_source_sha256", "import_batches", ["source_sha256"]
        )
