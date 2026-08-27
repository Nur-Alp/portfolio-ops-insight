"""Store operational action items (risk breach exceptions, accounting close
steps, ...) - deliberately separate from both DQ issue models. See
ActionItem's docstring in persistence/models.py for why.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_action_items"
down_revision = "0015_scope_published_uniqueness_to_uploader"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "action_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("domain", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("dataset_type", sa.String(80), nullable=True),
        sa.Column("scope_code", sa.String(120), nullable=True),
        sa.Column("reference_key", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("owner_id", sa.String(200), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by", sa.String(200), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignment_reason", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_action_item_domain_status", "action_items", ["domain", "status"])


def downgrade() -> None:
    op.drop_index("ix_action_item_domain_status", table_name="action_items")
    op.drop_table("action_items")
