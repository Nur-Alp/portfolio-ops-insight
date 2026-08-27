"""Do not retain dates inferred from arbitrary accounting cells."""

from alembic import op
import sqlalchemy as sa


revision = "0010_accounting_dates"
down_revision = "0009_osip_business_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Before the accounting landing parser required an explicit report-date
    # label, it selected the maximum date-shaped value in the sheet.  Existing
    # rows therefore cannot be repaired selectively from stored metadata: a
    # maturity date and a report date are indistinguishable after the fact.
    # Clear those inferred values.  A future re-import will populate dates only
    # when the workbook explicitly labels them; otherwise the UI shows
    # "Unavailable" rather than a misleading freshness date.
    datasets = sa.table(
        "dataset_versions",
        sa.column("dataset_type", sa.String()),
        sa.column("source_report_date", sa.Date()),
        sa.column("business_date", sa.Date()),
    )
    op.execute(
        datasets.update()
        .where(datasets.c.dataset_type == "accounting_landing")
        .values(source_report_date=None, business_date=None)
    )
    # ACCOUNTING-02 was emitted solely because the old parser compared
    # arbitrary date-shaped cells. It is not a valid finding after the parser
    # change and would otherwise remain visible on already-materialized data.
    op.execute(
        sa.text("""
            DELETE FROM dataset_issues
            WHERE code = 'ACCOUNTING-02'
              AND dataset_id IN (
                  SELECT id FROM dataset_versions
                  WHERE dataset_type = 'accounting_landing'
              )
        """)
    )


def downgrade() -> None:
    # The old inferred dates are not recoverable safely, so keep them unset.
    pass
