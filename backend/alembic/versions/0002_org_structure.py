"""org structure

Revision ID: 0002_org_structure
Revises: 0001_initial
Create Date: 2026-04-29 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_org_structure"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org_agents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("agent_type", sa.String(length=80), nullable=False),
        sa.Column("parent_agent_id", sa.Integer(), sa.ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("responsibilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("permissions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("budget_daily", sa.Float(), nullable=False),
        sa.Column("budget_monthly", sa.Float(), nullable=False),
        sa.Column("token_limit_daily", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("heartbeat_enabled", sa.Boolean(), nullable=False),
        sa.Column("heartbeat_cron", sa.String(length=120), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_org_agents_name", "org_agents", ["name"], unique=True)
    op.create_index("ix_org_agents_role", "org_agents", ["role"])
    op.create_index("ix_org_agents_status", "org_agents", ["status"])

    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_agent_id", sa.Integer(), sa.ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_metric", sa.String(length=120), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_goals_title", "goals", ["title"], unique=True)
    op.create_index("ix_goals_status", "goals", ["status"])

    op.create_table(
        "routines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_agent_id", sa.Integer(), sa.ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cron_schedule", sa.String(length=120), nullable=False),
        sa.Column("task_type", sa.String(length=120), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_routines_name", "routines", ["name"], unique=True)
    op.create_index("ix_routines_task_type", "routines", ["task_type"])

    op.create_table(
        "cost_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("tokens_input", sa.Integer(), nullable=False),
        sa.Column("tokens_output", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cost_events_agent_id", "cost_events", ["agent_id"])
    op.create_index("ix_cost_events_task_id", "cost_events", ["task_id"])
    op.create_index("ix_cost_events_created_at", "cost_events", ["created_at"])

    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_type", sa.String(length=80), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_activity_events_actor_type", "activity_events", ["actor_type"])
    op.create_index("ix_activity_events_actor_id", "activity_events", ["actor_id"])
    op.create_index("ix_activity_events_event_type", "activity_events", ["event_type"])
    op.create_index("ix_activity_events_entity_type", "activity_events", ["entity_type"])
    op.create_index("ix_activity_events_entity_id", "activity_events", ["entity_id"])
    op.create_index("ix_activity_events_created_at", "activity_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("activity_events")
    op.drop_table("cost_events")
    op.drop_table("routines")
    op.drop_table("goals")
    op.drop_table("org_agents")
