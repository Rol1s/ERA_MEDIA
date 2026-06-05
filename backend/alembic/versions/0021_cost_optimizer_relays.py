"""cost optimizer and relay channels

Revision ID: 0021_cost_optimizer_relays
Revises: 0020_newsroom_v1
Create Date: 2026-05-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0021_cost_optimizer_relays"
down_revision: str | None = "0020_newsroom_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("channels", sa.Column("channel_mode", sa.String(length=40), nullable=False, server_default="newsroom"))
    op.add_column("channels", sa.Column("relay_mode", sa.String(length=60), nullable=False, server_default=""))
    op.add_column("channels", sa.Column("relay_source_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("channels", sa.Column("relay_publish_delay_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("channels", sa.Column("relay_max_posts_per_day", sa.Integer(), nullable=False, server_default="0"))
    op.create_index(op.f("ix_channels_channel_mode"), "channels", ["channel_mode"], unique=False)

    op.create_table(
        "llm_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cache_key", sa.String(length=260), nullable=False),
        sa.Column("source_item_id", sa.Integer(), nullable=True),
        sa.Column("pipeline_step", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("input_hash", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tokens_saved_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["source_item_id"], ["source_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_llm_cache_cache_key"), "llm_cache", ["cache_key"], unique=True)
    op.create_index(op.f("ix_llm_cache_source_item_id"), "llm_cache", ["source_item_id"], unique=False)
    op.create_index(op.f("ix_llm_cache_pipeline_step"), "llm_cache", ["pipeline_step"], unique=False)
    op.create_index(op.f("ix_llm_cache_input_hash"), "llm_cache", ["input_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_cache_input_hash"), table_name="llm_cache")
    op.drop_index(op.f("ix_llm_cache_pipeline_step"), table_name="llm_cache")
    op.drop_index(op.f("ix_llm_cache_source_item_id"), table_name="llm_cache")
    op.drop_index(op.f("ix_llm_cache_cache_key"), table_name="llm_cache")
    op.drop_table("llm_cache")
    op.drop_index(op.f("ix_channels_channel_mode"), table_name="channels")
    op.drop_column("channels", "relay_max_posts_per_day")
    op.drop_column("channels", "relay_publish_delay_minutes")
    op.drop_column("channels", "relay_source_ids")
    op.drop_column("channels", "relay_mode")
    op.drop_column("channels", "channel_mode")
