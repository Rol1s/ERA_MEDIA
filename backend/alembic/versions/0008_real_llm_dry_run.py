"""real llm dry run metadata

Revision ID: 0008_real_llm_dry_run
Revises: 0007_operating_loop_kanban
Create Date: 2026-04-30 15:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_real_llm_dry_run"
down_revision: str | None = "0007_operating_loop_kanban"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("generation_mode", sa.String(length=40), nullable=False, server_default="mock"))
    op.add_column("posts", sa.Column("provider", sa.String(length=80), nullable=False, server_default="mock"))
    op.add_column("posts", sa.Column("model", sa.String(length=160), nullable=False, server_default="mock"))
    op.add_column("posts", sa.Column("prompt_template_version", sa.Integer(), nullable=True))
    op.add_column("posts", sa.Column("publishable", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("posts", sa.Column("non_publishable_reason", sa.Text(), nullable=False, server_default=""))
    op.add_column("posts", sa.Column("tokens_input", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("posts", sa.Column("tokens_output", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("posts", sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"))
    op.add_column("posts", sa.Column("llm_trace_id", sa.String(length=120), nullable=True))
    op.add_column("posts", sa.Column("structured_outputs_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_index("ix_posts_generation_mode", "posts", ["generation_mode"])
    op.create_index("ix_posts_publishable", "posts", ["publishable"])
    op.execute(
        """
        UPDATE posts
        SET generation_mode = CASE WHEN mock_only THEN 'mock' ELSE 'dry_run' END,
            provider = CASE WHEN mock_only THEN 'mock' ELSE created_by_agent END,
            model = CASE WHEN mock_only THEN 'mock' ELSE 'unknown' END,
            publishable = false,
            non_publishable_reason = CASE
                WHEN mock_only THEN COALESCE(NULLIF(not_publishable_reason, ''), 'Mock content is not publishable')
                ELSE 'Dry-run content requires human review'
            END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_posts_publishable", table_name="posts")
    op.drop_index("ix_posts_generation_mode", table_name="posts")
    op.drop_column("posts", "structured_outputs_json")
    op.drop_column("posts", "llm_trace_id")
    op.drop_column("posts", "estimated_cost_usd")
    op.drop_column("posts", "tokens_output")
    op.drop_column("posts", "tokens_input")
    op.drop_column("posts", "non_publishable_reason")
    op.drop_column("posts", "publishable")
    op.drop_column("posts", "prompt_template_version")
    op.drop_column("posts", "model")
    op.drop_column("posts", "provider")
    op.drop_column("posts", "generation_mode")
