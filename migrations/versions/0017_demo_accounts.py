"""Store fixed demo-persona login accounts for the self-issued 'demo'
identity provider - see DemoAccount's docstring in persistence/models.py.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_demo_accounts"
down_revision = "0016_action_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("roles", sa.String(200), nullable=False),
        sa.Column("domains", sa.String(200), nullable=False),
        sa.Column("portfolios", sa.String(200), nullable=False, server_default="*"),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("demo_accounts")
