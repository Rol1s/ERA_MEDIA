"""newsroom v1 media packaging and submissions

Revision ID: 0020_newsroom_v1
Revises: 0018_launch_ready
Create Date: 2026-05-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0020_newsroom_v1"
down_revision: str | None = "0018_launch_ready"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("media_source_type", sa.String(length=60), nullable=True, server_default="none"))
    op.add_column("posts", sa.Column("media_source_url", sa.Text(), nullable=True, server_default=""))
    op.add_column("posts", sa.Column("media_rights_note", sa.Text(), nullable=True, server_default=""))
    op.add_column("posts", sa.Column("media_status", sa.String(length=60), nullable=True, server_default="missing"))
    op.add_column("posts", sa.Column("max_packaged_text", sa.Text(), nullable=True, server_default=""))
    op.add_column("posts", sa.Column("max_buttons_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")))
    op.add_column("posts", sa.Column("operator_checklist_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")))
    op.create_index(op.f("ix_posts_media_source_type"), "posts", ["media_source_type"], unique=False)
    op.create_index(op.f("ix_posts_media_status"), "posts", ["media_status"], unique=False)

    op.create_table(
        "newsroom_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="new"),
        sa.Column("source", sa.String(length=60), nullable=False, server_default="telegram"),
        sa.Column("submitter_chat_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("submitter_name", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("topic_id", sa.Integer(), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_newsroom_submissions_status"), "newsroom_submissions", ["status"], unique=False)
    op.create_index(op.f("ix_newsroom_submissions_source"), "newsroom_submissions", ["source"], unique=False)
    op.create_index(op.f("ix_newsroom_submissions_submitter_chat_id"), "newsroom_submissions", ["submitter_chat_id"], unique=False)
    op.create_index(op.f("ix_newsroom_submissions_topic_id"), "newsroom_submissions", ["topic_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_newsroom_submissions_topic_id"), table_name="newsroom_submissions")
    op.drop_index(op.f("ix_newsroom_submissions_submitter_chat_id"), table_name="newsroom_submissions")
    op.drop_index(op.f("ix_newsroom_submissions_source"), table_name="newsroom_submissions")
    op.drop_index(op.f("ix_newsroom_submissions_status"), table_name="newsroom_submissions")
    op.drop_table("newsroom_submissions")
    op.drop_index(op.f("ix_posts_media_status"), table_name="posts")
    op.drop_index(op.f("ix_posts_media_source_type"), table_name="posts")
    op.drop_column("posts", "operator_checklist_json")
    op.drop_column("posts", "max_buttons_json")
    op.drop_column("posts", "max_packaged_text")
    op.drop_column("posts", "media_status")
    op.drop_column("posts", "media_rights_note")
    op.drop_column("posts", "media_source_url")
    op.drop_column("posts", "media_source_type")
