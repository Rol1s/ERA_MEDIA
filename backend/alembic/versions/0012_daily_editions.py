"""daily editions

Revision ID: 0012_daily_editions
Revises: 0011_source_items_ingestion
Create Date: 2026-05-07 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_daily_editions"
down_revision: Union[str, None] = "0014_task_archive_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "daily_editions" not in inspector.get_table_names():
        op.create_table(
            "daily_editions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="collecting"),
            sa.Column("target_topics_count", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("target_posts_count", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("selected_topics_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("generated_posts_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("approved_posts_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rejected_posts_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("editor_notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_editions_date ON daily_editions (date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_editions_channel_id ON daily_editions (channel_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_editions_status ON daily_editions (status)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_daily_editions_date_channel'
            ) THEN
                ALTER TABLE daily_editions ADD CONSTRAINT uq_daily_editions_date_channel UNIQUE (date, channel_id);
            END IF;
        END $$;
        """
    )

    op.execute("ALTER TABLE topics ADD COLUMN IF NOT EXISTS daily_edition_id INTEGER")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_topics_daily_edition_id'
            ) THEN
                ALTER TABLE topics ADD CONSTRAINT fk_topics_daily_edition_id
                FOREIGN KEY (daily_edition_id) REFERENCES daily_editions(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_topics_daily_edition_id ON topics (daily_edition_id)")

    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS daily_edition_id INTEGER")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_posts_daily_edition_id'
            ) THEN
                ALTER TABLE posts ADD CONSTRAINT fk_posts_daily_edition_id
                FOREIGN KEY (daily_edition_id) REFERENCES daily_editions(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_posts_daily_edition_id ON posts (daily_edition_id)")


def downgrade() -> None:
    op.drop_index("ix_posts_daily_edition_id", table_name="posts")
    op.drop_constraint("fk_posts_daily_edition_id", "posts", type_="foreignkey")
    op.drop_column("posts", "daily_edition_id")
    op.drop_index("ix_topics_daily_edition_id", table_name="topics")
    op.drop_constraint("fk_topics_daily_edition_id", "topics", type_="foreignkey")
    op.drop_column("topics", "daily_edition_id")
    op.drop_constraint("uq_daily_editions_date_channel", "daily_editions", type_="unique")
    op.drop_index("ix_daily_editions_status", table_name="daily_editions")
    op.drop_index("ix_daily_editions_channel_id", table_name="daily_editions")
    op.drop_index("ix_daily_editions_date", table_name="daily_editions")
    op.drop_table("daily_editions")
