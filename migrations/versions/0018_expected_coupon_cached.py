"""Persist OSIP's cached expected-coupon amount, resolved by header label.

Previously read at export time straight from a hardcoded raw-row column
index (see services/holdings_export/coupons.py), which broke silently when
the OSIP generator's column layout shifted. Now resolved once at parse time
via the same label-based column contract as every other field.
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_expected_coupon_cached"
down_revision = "0017_demo_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "position_lots",
        sa.Column("expected_coupon_cached", sa.Numeric(38, 12), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("position_lots", "expected_coupon_cached")
