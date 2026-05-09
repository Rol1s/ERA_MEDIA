"""unschedule non publishable posts

Revision ID: 0009_unschedule_nonpub
Revises: 0008_real_llm_dry_run
Create Date: 2026-04-30 17:35:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0009_unschedule_nonpub"
down_revision: Union[str, None] = "0008_real_llm_dry_run"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE posts
        SET status = 'needs_review',
            scheduled_at = NULL,
            status_reason = 'Non-publishable mock/dry-run post cannot remain scheduled'
        WHERE status = 'scheduled'
          AND publishable IS FALSE
          AND generation_mode IN ('mock', 'dry_run')
        """
    )


def downgrade() -> None:
    pass
