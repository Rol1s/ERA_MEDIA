"""control plane integrations notifications issues

Revision ID: 0004_control_plane
Revises: 0003_safety_controls
Create Date: 2026-04-29 00:00:03.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_control_plane"
down_revision: str | None = "0003_safety_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("org_agents", sa.Column("supervises", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False))
    op.add_column("org_agents", sa.Column("reviewed_by", sa.String(length=140), server_default="", nullable=False))
    op.add_column("org_agents", sa.Column("can_create_tasks", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("org_agents", sa.Column("can_approve_posts", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("org_agents", sa.Column("can_publish", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("org_agents", sa.Column("can_spend_budget", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    op.create_table(
        "integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("secret_ref", sa.String(length=240), nullable=False),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_integrations_name", "integrations", ["name"], unique=True)
    op.create_index("ix_integrations_provider", "integrations", ["provider"])
    op.create_index("ix_integrations_type", "integrations", ["type"])
    op.create_index("ix_integrations_status", "integrations", ["status"])

    op.create_table(
        "platform_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(length=80), nullable=False),
        sa.Column("external_chat_id", sa.String(length=240), nullable=False),
        sa.Column("external_channel_url", sa.Text(), nullable=False),
        sa.Column("integration_id", sa.Integer(), sa.ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("publish_mode", sa.String(length=60), nullable=False),
        sa.Column("can_publish", sa.Boolean(), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_platform_channels_channel_id", "platform_channels", ["channel_id"])
    op.create_index("ix_platform_channels_platform", "platform_channels", ["platform"])
    op.create_index("ix_platform_channels_status", "platform_channels", ["status"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_severity", "notifications", ["severity"])
    op.create_index("ix_notifications_entity_type", "notifications", ["entity_type"])
    op.create_index("ix_notifications_entity_id", "notifications", ["entity_id"])
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=260), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("issue_type", sa.String(length=80), nullable=False),
        sa.Column("owner_agent_id", sa.Integer(), sa.ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewer_agent_id", sa.Integer(), sa.ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("priority", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_issues_title", "issues", ["title"])
    op.create_index("ix_issues_issue_type", "issues", ["issue_type"])
    op.create_index("ix_issues_owner_agent_id", "issues", ["owner_agent_id"])
    op.create_index("ix_issues_reviewer_agent_id", "issues", ["reviewer_agent_id"])
    op.create_index("ix_issues_related_channel_id", "issues", ["related_channel_id"])
    op.create_index("ix_issues_related_topic_id", "issues", ["related_topic_id"])
    op.create_index("ix_issues_related_post_id", "issues", ["related_post_id"])
    op.create_index("ix_issues_priority", "issues", ["priority"])
    op.create_index("ix_issues_status", "issues", ["status"])

    op.create_table(
        "decision_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("alternatives_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_decision_logs_agent_run_id", "decision_logs", ["agent_run_id"])
    op.create_index("ix_decision_logs_issue_id", "decision_logs", ["issue_id"])
    op.create_index("ix_decision_logs_entity_type", "decision_logs", ["entity_type"])
    op.create_index("ix_decision_logs_entity_id", "decision_logs", ["entity_id"])
    op.create_index("ix_decision_logs_decision", "decision_logs", ["decision"])
    op.create_index("ix_decision_logs_created_at", "decision_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("decision_logs")
    op.drop_table("issues")
    op.drop_table("notifications")
    op.drop_table("platform_channels")
    op.drop_table("integrations")
    op.drop_column("org_agents", "can_spend_budget")
    op.drop_column("org_agents", "can_publish")
    op.drop_column("org_agents", "can_approve_posts")
    op.drop_column("org_agents", "can_create_tasks")
    op.drop_column("org_agents", "reviewed_by")
    op.drop_column("org_agents", "supervises")
