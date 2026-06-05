"""launch readiness manual metrics

Revision ID: 0018_launch_ready
Revises: 0012_daily_editions
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0018_launch_ready"
down_revision = "0012_daily_editions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("published_url", sa.Text(), nullable=False, server_default=""))
    op.add_column("posts", sa.Column("manual_publish_note", sa.Text(), nullable=False, server_default=""))
    op.add_column("metrics", sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="SET NULL"), nullable=True))
    op.add_column("metrics", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("metrics", sa.Column("subscribers_before", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("metrics", sa.Column("subscribers_after", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("metrics", sa.Column("link_clicks", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("metrics", sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"))
    op.create_index("ix_metrics_channel_id", "metrics", ["channel_id"])
    op.create_index("ix_metrics_source", "metrics", ["source"])
    op.create_table(
        "archived_generated_content",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("generation_mode", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("archive_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_archived_generated_content_entity_type", "archived_generated_content", ["entity_type"])
    op.create_index("ix_archived_generated_content_entity_id", "archived_generated_content", ["entity_id"])
    op.create_index("ix_archived_generated_content_generation_mode", "archived_generated_content", ["generation_mode"])
    op.create_index("ix_archived_generated_content_provider", "archived_generated_content", ["provider"])
    op.create_index("ix_archived_generated_content_status", "archived_generated_content", ["status"])


def downgrade() -> None:
    op.drop_index("ix_archived_generated_content_status", table_name="archived_generated_content")
    op.drop_index("ix_archived_generated_content_provider", table_name="archived_generated_content")
    op.drop_index("ix_archived_generated_content_generation_mode", table_name="archived_generated_content")
    op.drop_index("ix_archived_generated_content_entity_id", table_name="archived_generated_content")
    op.drop_index("ix_archived_generated_content_entity_type", table_name="archived_generated_content")
    op.drop_table("archived_generated_content")
    op.drop_index("ix_metrics_source", table_name="metrics")
    op.drop_index("ix_metrics_channel_id", table_name="metrics")
    op.drop_column("metrics", "source")
    op.drop_column("metrics", "link_clicks")
    op.drop_column("metrics", "subscribers_after")
    op.drop_column("metrics", "subscribers_before")
    op.drop_column("metrics", "published_at")
    op.drop_column("metrics", "channel_id")
    op.drop_column("posts", "manual_publish_note")
    op.drop_column("posts", "published_url")
