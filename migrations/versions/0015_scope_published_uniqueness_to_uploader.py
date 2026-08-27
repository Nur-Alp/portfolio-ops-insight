"""Scope the one-published-version-per-date constraint to the uploader.

Per-uploader visibility (see 0014 and _has_uploader_access in
routes/multi_source.py) means two operators can each have their own
published version for the same dataset_type/scope_code/business_date.
Without uploader_id in this constraint, one operator's publish would
collide with - and supersede - a different operator's publish for the
same date, even though that operator's data is otherwise invisible to
them.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0015_scope_published_uniqueness_to_uploader"
down_revision = "0014_scope_source_hash_to_uploader"
branch_labels = None
depends_on = None

_NEW_COLUMNS = ["dataset_type", "scope_code", "business_date", "uploader_id"]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            'DROP INDEX IF EXISTS uq_published_dataset_scope_date'
        )
        op.create_index(
            "uq_published_dataset_scope_date",
            "dataset_versions",
            _NEW_COLUMNS,
            unique=True,
            postgresql_where=sa.text("status = 'published'"),
        )
        return

    # SQLite's partial index has no ALTER form - drop and recreate it
    # directly rather than rebuilding the whole table (unlike 0014, this is
    # an index, not a table-level UniqueConstraint/auto-index).
    op.execute("DROP INDEX IF EXISTS uq_published_dataset_scope_date")
    op.execute(
        "CREATE UNIQUE INDEX uq_published_dataset_scope_date "
        "ON dataset_versions (dataset_type, scope_code, business_date, uploader_id) "
        "WHERE status = 'published'"
    )


def downgrade() -> None:
    # Once two uploaders have each published a version for the same date
    # (exactly what this migration allows), recreating the narrower index
    # could fail on a genuine duplicate rather than a design mistake. Leave
    # the widened ownership model in place rather than guessing which
    # uploader's row should be treated as the surviving one.
    pass
