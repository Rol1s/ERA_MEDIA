"""llm provider configs prompts and issue delegation

Revision ID: 0005_llm_control_plane
Revises: 0004_control_plane
Create Date: 2026-04-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_llm_control_plane"
down_revision: str | None = "0004_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("provider", sa.String(length=80), nullable=False, server_default="mock"))
    op.add_column("agent_runs", sa.Column("model", sa.String(length=160), nullable=False, server_default="mock"))
    op.add_column("agent_runs", sa.Column("prompt_template_id", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("prompt_version", sa.Integer(), nullable=True))
    op.create_index("ix_agent_runs_prompt_template_id", "agent_runs", ["prompt_template_id"])

    op.add_column("issues", sa.Column("parent_issue_id", sa.Integer(), nullable=True))
    op.add_column("issues", sa.Column("root_issue_id", sa.Integer(), nullable=True))
    op.add_column("issues", sa.Column("delegation_level", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("issues", sa.Column("blocked_by_issue_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_issues_parent_issue_id", "issues", "issues", ["parent_issue_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_issues_root_issue_id", "issues", "issues", ["root_issue_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_issues_blocked_by_issue_id", "issues", "issues", ["blocked_by_issue_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_issues_parent_issue_id", "issues", ["parent_issue_id"])
    op.create_index("ix_issues_root_issue_id", "issues", ["root_issue_id"])
    op.create_index("ix_issues_blocked_by_issue_id", "issues", ["blocked_by_issue_id"])

    op.create_table(
        "llm_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("label", sa.String(length=220), nullable=False),
        sa.Column("input_cost_per_1m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("output_cost_per_1m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("supports_tools", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("supports_json_schema", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_llm_models_provider", "llm_models", ["provider"])
    op.create_index("ix_llm_models_model", "llm_models", ["model"])

    op.create_table(
        "agent_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_agent_id", sa.Integer(), sa.ForeignKey("org_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default="mock"),
        sa.Column("model", sa.String(length=160), nullable=False, server_default="mock"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="800"),
        sa.Column("system_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("tools_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("daily_budget_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("daily_token_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_runs_per_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_agent_id"),
    )
    op.create_index("ix_agent_configs_org_agent_id", "agent_configs", ["org_agent_id"])
    op.create_index("ix_agent_configs_provider", "agent_configs", ["provider"])

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("agent_type", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_templates_name", "prompt_templates", ["name"])
    op.create_index("ix_prompt_templates_agent_type", "prompt_templates", ["agent_type"])
    op.create_index("ix_prompt_templates_version", "prompt_templates", ["version"])
    op.create_index("ix_prompt_templates_status", "prompt_templates", ["status"])


def downgrade() -> None:
    op.drop_table("prompt_templates")
    op.drop_table("agent_configs")
    op.drop_table("llm_models")
    op.drop_index("ix_issues_blocked_by_issue_id", table_name="issues")
    op.drop_index("ix_issues_root_issue_id", table_name="issues")
    op.drop_index("ix_issues_parent_issue_id", table_name="issues")
    op.drop_constraint("fk_issues_blocked_by_issue_id", "issues", type_="foreignkey")
    op.drop_constraint("fk_issues_root_issue_id", "issues", type_="foreignkey")
    op.drop_constraint("fk_issues_parent_issue_id", "issues", type_="foreignkey")
    op.drop_column("issues", "blocked_by_issue_id")
    op.drop_column("issues", "delegation_level")
    op.drop_column("issues", "root_issue_id")
    op.drop_column("issues", "parent_issue_id")
    op.drop_index("ix_agent_runs_prompt_template_id", table_name="agent_runs")
    op.drop_column("agent_runs", "prompt_version")
    op.drop_column("agent_runs", "prompt_template_id")
    op.drop_column("agent_runs", "model")
    op.drop_column("agent_runs", "provider")
