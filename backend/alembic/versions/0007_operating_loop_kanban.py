"""agent managed kanban and operating loop

Revision ID: 0007_operating_loop_kanban
Revises: 0006_agent_cfg_prompt
Create Date: 2026-04-30 09:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_operating_loop_kanban"
down_revision: str | None = "0006_agent_cfg_prompt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("mock_only", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("posts", sa.Column("not_publishable_reason", sa.Text(), nullable=False, server_default=""))
    op.create_index("ix_posts_mock_only", "posts", ["mock_only"])

    op.add_column("issues", sa.Column("next_action", sa.Text(), nullable=False, server_default=""))
    op.add_column("issues", sa.Column("blocked_reason", sa.Text(), nullable=False, server_default=""))
    op.add_column("issues", sa.Column("required_human_action", sa.Text(), nullable=False, server_default=""))
    op.add_column("issues", sa.Column("target_metric", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("issues", sa.Column("target_value", sa.Float(), nullable=False, server_default="0"))
    op.add_column("issues", sa.Column("current_value", sa.Float(), nullable=False, server_default="0"))
    op.add_column("issues", sa.Column("progress_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("issues", sa.Column("idempotency_key", sa.String(length=260), nullable=True))
    op.create_index("ix_issues_idempotency_key", "issues", ["idempotency_key"], unique=True)
    op.execute("UPDATE issues SET status = 'backlog' WHERE status = 'open'")
    op.execute("UPDATE issues SET status = 'review' WHERE status = 'waiting_review'")
    op.execute("UPDATE issues SET status = 'review' WHERE status = 'scheduled'")

    op.create_table(
        "operating_loop_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mode", sa.String(length=60), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("planning_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=60), nullable=False, server_default="running"),
        sa.Column("report_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("issues_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issues_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issues_moved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decisions_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_operating_loop_runs_mode", "operating_loop_runs", ["mode"])
    op.create_index("ix_operating_loop_runs_action", "operating_loop_runs", ["action"])
    op.create_index("ix_operating_loop_runs_planning_only", "operating_loop_runs", ["planning_only"])
    op.create_index("ix_operating_loop_runs_status", "operating_loop_runs", ["status"])
    op.create_index("ix_operating_loop_runs_started_at", "operating_loop_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_operating_loop_runs_started_at", table_name="operating_loop_runs")
    op.drop_index("ix_operating_loop_runs_status", table_name="operating_loop_runs")
    op.drop_index("ix_operating_loop_runs_planning_only", table_name="operating_loop_runs")
    op.drop_index("ix_operating_loop_runs_action", table_name="operating_loop_runs")
    op.drop_index("ix_operating_loop_runs_mode", table_name="operating_loop_runs")
    op.drop_table("operating_loop_runs")

    op.execute("UPDATE issues SET status = 'open' WHERE status = 'backlog'")
    op.execute("UPDATE issues SET status = 'waiting_review' WHERE status = 'review'")
    op.drop_index("ix_issues_idempotency_key", table_name="issues")
    op.drop_column("issues", "idempotency_key")
    op.drop_column("issues", "progress_json")
    op.drop_column("issues", "current_value")
    op.drop_column("issues", "target_value")
    op.drop_column("issues", "target_metric")
    op.drop_column("issues", "required_human_action")
    op.drop_column("issues", "blocked_reason")
    op.drop_column("issues", "next_action")

    op.drop_index("ix_posts_mock_only", table_name="posts")
    op.drop_column("posts", "not_publishable_reason")
    op.drop_column("posts", "mock_only")
