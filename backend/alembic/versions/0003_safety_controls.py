"""safety controls and editability

Revision ID: 0003_safety_controls
Revises: 0002_org_structure
Create Date: 2026-04-29 00:00:02.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_safety_controls"
down_revision: str | None = "0002_org_structure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)

    op.add_column("channels", sa.Column("daily_post_limit", sa.Integer(), server_default="1", nullable=False))
    op.add_column("channels", sa.Column("publish_mode", sa.String(length=40), server_default="manual", nullable=False))

    op.add_column("sources", sa.Column("requires_review", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("sources", sa.Column("last_error", sa.Text(), server_default="", nullable=False))
    op.add_column("sources", sa.Column("health_status", sa.String(length=40), server_default="unknown", nullable=False))
    op.add_column("sources", sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    op.add_column("topics", sa.Column("why_this_matters", sa.Text(), server_default="", nullable=False))
    op.add_column("topics", sa.Column("suggested_angle", sa.Text(), server_default="", nullable=False))
    op.add_column("topics", sa.Column("assigned_channel_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False))
    op.add_column("topics", sa.Column("is_duplicate", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("topics", sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    op.add_column("posts", sa.Column("status_reason", sa.Text(), server_default="", nullable=False))
    op.add_column("posts", sa.Column("risk_reason", sa.Text(), server_default="", nullable=False))
    op.add_column("posts", sa.Column("quality_reason", sa.Text(), server_default="", nullable=False))
    op.add_column("posts", sa.Column("version_history", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False))
    op.add_column("posts", sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    op.add_column("routines", sa.Column("max_runs_per_day", sa.Integer(), server_default="1", nullable=False))
    op.add_column("routines", sa.Column("max_budget_per_run", sa.Float(), server_default="0", nullable=False))
    op.add_column("routines", sa.Column("last_run_status", sa.String(length=80), server_default="never", nullable=False))

    op.add_column("cost_events", sa.Column("channel_id", sa.Integer(), nullable=True))
    op.add_column("cost_events", sa.Column("task_type", sa.String(length=120), server_default="unknown", nullable=False))
    op.create_foreign_key("fk_cost_events_channel_id_channels", "cost_events", "channels", ["channel_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_cost_events_channel_id", "cost_events", ["channel_id"])
    op.create_index("ix_cost_events_task_type", "cost_events", ["task_type"])


def downgrade() -> None:
    op.drop_index("ix_cost_events_task_type", table_name="cost_events")
    op.drop_index("ix_cost_events_channel_id", table_name="cost_events")
    op.drop_constraint("fk_cost_events_channel_id_channels", "cost_events", type_="foreignkey")
    op.drop_column("cost_events", "task_type")
    op.drop_column("cost_events", "channel_id")

    op.drop_column("routines", "last_run_status")
    op.drop_column("routines", "max_budget_per_run")
    op.drop_column("routines", "max_runs_per_day")

    op.drop_column("posts", "is_demo")
    op.drop_column("posts", "version_history")
    op.drop_column("posts", "quality_reason")
    op.drop_column("posts", "risk_reason")
    op.drop_column("posts", "status_reason")

    op.drop_column("topics", "is_demo")
    op.drop_column("topics", "is_duplicate")
    op.drop_column("topics", "assigned_channel_ids")
    op.drop_column("topics", "suggested_angle")
    op.drop_column("topics", "why_this_matters")

    op.drop_column("sources", "is_demo")
    op.drop_column("sources", "health_status")
    op.drop_column("sources", "last_error")
    op.drop_column("sources", "requires_review")

    op.drop_column("channels", "publish_mode")
    op.drop_column("channels", "daily_post_limit")

    op.drop_table("system_settings")
