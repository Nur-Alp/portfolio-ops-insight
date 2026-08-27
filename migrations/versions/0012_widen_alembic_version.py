"""Allow the historical carrying-price revision identifier to be stored."""

from alembic import op
import sqlalchemy as sa


revision = "0012_widen_alembic_version"
down_revision = "0011_carrying_price_native"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL enforces the default VARCHAR(32) length on alembic_version;
    # SQLite does not.  Widen before the following migration writes its
    # 35-character compatibility revision identifier.
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
            existing_nullable=False,
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=64),
            type_=sa.String(length=32),
            existing_nullable=False,
        )
