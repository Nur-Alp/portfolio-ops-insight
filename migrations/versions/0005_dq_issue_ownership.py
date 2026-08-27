"""Add owner and due date to data quality issues.

Revision ID: 0005_dq_issue_ownership
Revises: 0004_retry_rejected_failed

Kept to 32 characters: PostgreSQL's default alembic_version.version_num
column is VARCHAR(32) and silently truncates on SQLite but errors on
PostgreSQL, so every revision id here must stay at or under that length.
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_dq_issue_ownership"
down_revision = "0004_retry_rejected_failed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "data_quality_issues", sa.Column("owner_id", sa.String(200), nullable=True)
    )
    op.add_column(
        "data_quality_issues", sa.Column("due_date", sa.Date(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("data_quality_issues", "due_date")
    op.drop_column("data_quality_issues", "owner_id")
