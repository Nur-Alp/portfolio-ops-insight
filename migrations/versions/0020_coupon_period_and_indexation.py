"""Persist the source's own coupon period (days) and coupon-indexation factor.

Needed to reproduce OSIP's real "Сумма ожидаемого купона" formula exactly
(``IF(period=180, nominal*qty*rate/2, IF(period=360, ..., ...*365*period))) *
indexation``) when its own cached formula result is blank - confirmed via
LibreOffice recalculation of a real workbook. The parser previously inferred
a payment frequency from the calendar gap between coupon dates instead of
reading the real period, which matched for standard periods (180/360/30/90
days) but understated an irregular "stub" period by double digits of percent
(a real 211-day stub was 13.5% short). See
``services/holdings_export/coupons.py``'s ``_derive_expected_coupon_native``.
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_coupon_period_and_indexation"
down_revision = "0019_osip_resolved_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "position_lots",
        sa.Column("coupon_period_days", sa.Numeric(38, 12), nullable=True),
    )
    op.add_column(
        "position_lots",
        sa.Column("coupon_indexation", sa.Numeric(38, 12), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("position_lots", "coupon_indexation")
    op.drop_column("position_lots", "coupon_period_days")
