"""Persist the OSIP current YTM field for each immutable source lot."""

from alembic import op
import sqlalchemy as sa
from decimal import Decimal, InvalidOperation


revision = "0006_current_ytm"
down_revision = "0005_dq_issue_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "position_lots", sa.Column("current_ytm", sa.Numeric(38, 12), nullable=True)
    )
    # Existing immutable snapshots retain their raw OSIP rows. Backfill the
    # newly persisted field from column Z (zero-based index 25) so local and
    # production history becomes usable without a re-upload.
    connection = op.get_bind()
    metadata = sa.MetaData()
    lots = sa.Table("position_lots", metadata, autoload_with=connection)
    source_rows = sa.Table("source_rows", metadata, autoload_with=connection)
    rows = connection.execute(
        sa.select(lots.c.id, source_rows.c.raw_values).join(
            source_rows, lots.c.source_row_id == source_rows.c.id
        )
    )
    for lot_id, raw_values in rows:
        if not isinstance(raw_values, list) or len(raw_values) <= 25:
            continue
        value = raw_values[25]
        if value in (None, ""):
            continue
        try:
            current_ytm = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            continue
        connection.execute(
            lots.update().where(lots.c.id == lot_id).values(current_ytm=current_ytm)
        )


def downgrade() -> None:
    op.drop_column("position_lots", "current_ytm")
