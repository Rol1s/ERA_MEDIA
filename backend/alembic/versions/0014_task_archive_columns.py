"""compatibility bridge for existing deployed task archive migration

Revision ID: 0014_task_archive_columns
Revises: 0011_source_items_ingestion
Create Date: 2026-05-07 11:55:00.000000

The production database may already be stamped with this revision from an
earlier working directory. Keep this migration as a no-op bridge so the current
project can continue from the deployed database state without rebuilding broad
infrastructure.
"""

from typing import Sequence, Union

revision: str = "0014_task_archive_columns"
down_revision: Union[str, None] = "0011_source_items_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
