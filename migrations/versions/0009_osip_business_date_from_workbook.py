"""Use the parsed workbook date for legacy OSIP business dates."""

from alembic import op
import sqlalchemy as sa


revision = "0009_osip_business_date"
down_revision = "0008_client_identity_resolutions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older OSIP rows used a date parsed from the filename. For a classic
    # portfolio snapshot, source_report_date is the date parsed from the
    # workbook and is the only valid business date. This repairs existing
    # metadata without touching source files, snapshots, or financial values.
    import_batches = sa.table(
        "import_batches",
        sa.column("dataset_type", sa.String()),
        sa.column("source_report_date", sa.Date()),
        sa.column("business_date", sa.Date()),
    )
    op.execute(
        import_batches.update()
        .where(import_batches.c.dataset_type == "portfolio_snapshot")
        .where(import_batches.c.source_report_date.is_not(None))
        .values(business_date=import_batches.c.source_report_date)
    )


def downgrade() -> None:
    # The previous filename-derived values are not recoverable from governed
    # source data, so downgrade intentionally leaves the corrected metadata.
    pass
