"""source items ingestion

Revision ID: 0011_source_items_ingestion
Revises: 0010_integration_secrets
Create Date: 2026-05-01 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_source_items_ingestion"
down_revision: Union[str, None] = "0010_integration_secrets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_html_hash", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("extracted_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("content_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extraction_status", sa.String(length=40), nullable=False, server_default="fetched"),
        sa.Column("extraction_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("paywall_or_blocked_detected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duplicate_of_item_id", sa.Integer(), sa.ForeignKey("source_items.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_source_items_source_id", "source_items", ["source_id"])
    op.create_index("ix_source_items_url", "source_items", ["url"])
    op.create_index("ix_source_items_canonical_url", "source_items", ["canonical_url"])
    op.create_index("ix_source_items_published_at", "source_items", ["published_at"])
    op.create_index("ix_source_items_raw_html_hash", "source_items", ["raw_html_hash"])
    op.create_index("ix_source_items_extraction_status", "source_items", ["extraction_status"])
    op.create_index("ix_source_items_duplicate_of_item_id", "source_items", ["duplicate_of_item_id"])

    op.add_column("topics", sa.Column("source_item_id", sa.Integer(), nullable=True))
    op.add_column("topics", sa.Column("extraction_status", sa.String(length=40), nullable=False, server_default=""))
    op.add_column("topics", sa.Column("extraction_error", sa.Text(), nullable=False, server_default=""))
    op.add_column("topics", sa.Column("content_length", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("topics", sa.Column("language", sa.String(length=20), nullable=False, server_default=""))
    op.add_column("topics", sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("topics", sa.Column("canonical_url", sa.Text(), nullable=False, server_default=""))
    op.add_column("topics", sa.Column("paywall_or_blocked_detected", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key("fk_topics_source_item_id", "topics", "source_items", ["source_item_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_topics_source_item_id", "topics", ["source_item_id"])


def downgrade() -> None:
    op.drop_index("ix_topics_source_item_id", table_name="topics")
    op.drop_constraint("fk_topics_source_item_id", "topics", type_="foreignkey")
    op.drop_column("topics", "paywall_or_blocked_detected")
    op.drop_column("topics", "canonical_url")
    op.drop_column("topics", "source_published_at")
    op.drop_column("topics", "language")
    op.drop_column("topics", "content_length")
    op.drop_column("topics", "extraction_error")
    op.drop_column("topics", "extraction_status")
    op.drop_column("topics", "source_item_id")
    op.drop_index("ix_source_items_duplicate_of_item_id", table_name="source_items")
    op.drop_index("ix_source_items_extraction_status", table_name="source_items")
    op.drop_index("ix_source_items_raw_html_hash", table_name="source_items")
    op.drop_index("ix_source_items_published_at", table_name="source_items")
    op.drop_index("ix_source_items_canonical_url", table_name="source_items")
    op.drop_index("ix_source_items_url", table_name="source_items")
    op.drop_index("ix_source_items_source_id", table_name="source_items")
    op.drop_table("source_items")
