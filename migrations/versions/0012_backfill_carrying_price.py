"""Backfill OSIP balance prices from immutable source-row payloads."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from alembic import op
import sqlalchemy as sa


# Keep the historical revision identifier used by existing local databases.
# The migration file was renamed, but changing the identifier would make a
# persisted dashboard database appear to reference a missing revision.
revision = "0012_backfill_carrying_price_native"
down_revision = "0012_widen_alembic_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT position_lots.id, source_rows.raw_values
            FROM position_lots
            JOIN source_rows ON source_rows.id = position_lots.source_row_id
            WHERE position_lots.carrying_price_native IS NULL
            """
        )
    ).fetchall()
    for lot_id, raw_values in rows:
        if isinstance(raw_values, str):
            try:
                raw_values = json.loads(raw_values)
            except json.JSONDecodeError:
                continue
        if not isinstance(raw_values, list) or len(raw_values) <= 24:
            continue
        value = raw_values[24]
        if value in (None, ""):
            continue
        try:
            price = Decimal(str(value))
        except (InvalidOperation, ValueError):
            continue
        # Use a textual predicate here because SQLite stores UUID primary keys
        # as text while SQLAlchemy's typed UUID binder expects a UUID object.
        connection.execute(
            sa.text(
                "UPDATE position_lots SET carrying_price_native = :price WHERE id = :lot_id"
            ),
            {"price": str(price), "lot_id": str(lot_id)},
        )


def downgrade() -> None:
    # The field itself is owned by migration 0011; this migration only restores
    # values that were already present in immutable source rows.
    pass
