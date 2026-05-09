"""agent config prompt template override

Revision ID: 0006_agent_cfg_prompt
Revises: 0005_llm_control_plane
Create Date: 2026-04-30 08:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_agent_cfg_prompt"
down_revision: str | None = "0005_llm_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_configs", sa.Column("prompt_template_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_agent_configs_prompt_template_id",
        "agent_configs",
        "prompt_templates",
        ["prompt_template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_agent_configs_prompt_template_id", "agent_configs", ["prompt_template_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_configs_prompt_template_id", table_name="agent_configs")
    op.drop_constraint("fk_agent_configs_prompt_template_id", "agent_configs", type_="foreignkey")
    op.drop_column("agent_configs", "prompt_template_id")
