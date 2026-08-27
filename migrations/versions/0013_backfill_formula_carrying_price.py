"""Backfill formula-backed OSIP balance prices from immutable source rows.

Some OSIP workbooks store the balance-price formula without an Excel cached
result.  The parser now evaluates that formula on import; this migration
applies the same documented calculation to already-imported evidence.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from alembic import op
import sqlalchemy as sa


revision = "0013_backfill_formula_carrying_price"
down_revision = "0012_backfill_carrying_price_native"
branch_labels = None
depends_on = None


def _decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _formula_carrying_price(values: list[object]) -> Decimal | None:
    """Mirror OSIP's formula in Excel columns Q, L, AA, BE and BF.

    =IF(Q=0,0,IF(OR(AA=0,ISBLANK(AA)),"",IF(BF=4,AA/Q,
      IF(BE=3,AA/Q,AA/Q/L*100))))
    """

    if len(values) <= 57:
        return None
    quantity = _decimal(values[16])
    carrying_amount = _decimal(values[26])
    nominal = _decimal(values[11])
    branch_bf = _decimal(values[57])
    branch_be = _decimal(values[56])
    if quantity is None:
        return None
    if quantity == 0:
        return Decimal("0")
    if carrying_amount is None or carrying_amount == 0:
        return None
    if branch_bf == 4 or branch_be == 3:
        return carrying_amount / quantity
    if nominal is None or nominal == 0:
        return None
    return carrying_amount / quantity / nominal * 100


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
        if not isinstance(raw_values, list):
            continue
        price = _formula_carrying_price(raw_values)
        if price is None:
            continue
        connection.execute(
            sa.text(
                "UPDATE position_lots SET carrying_price_native = :price WHERE id = :lot_id"
            ),
            {"price": str(price), "lot_id": str(lot_id)},
        )


def downgrade() -> None:
    # Values are derived from immutable source rows; do not erase them on
    # downgrade because the preceding migration may have restored real source
    # values and the records may already be published.
    pass
