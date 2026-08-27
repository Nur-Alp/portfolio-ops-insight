"""Persist OSIP's source balance price in the purchase-price quote basis."""

from alembic import op
import sqlalchemy as sa


revision = "0011_carrying_price_native"
down_revision = "0010_accounting_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "position_lots",
        sa.Column("carrying_price_native", sa.Numeric(38, 12), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("position_lots", "carrying_price_native")
