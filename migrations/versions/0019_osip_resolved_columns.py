"""Persist each OSIP import's resolved header-label column map.

Provenance lookups (snapshot_provenance, DQ issue source cells) previously
assumed one fixed column position per field across every OSIP import - see
the hardcoded _OSIP_SOURCE_COLUMNS map in api_handlers/snapshots.py. That
broke the same way the parser itself did (columns move when the generator's
template changes): the provenance "jump to source cell" pointer would now
silently point at the wrong physical cell for imports parsed under a new
layout. Persisting the per-import resolved map lets provenance use the
column contract that import actually parsed under.
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_osip_resolved_columns"
down_revision = "0018_expected_coupon_cached"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("osip_resolved_columns", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_batches", "osip_resolved_columns")
