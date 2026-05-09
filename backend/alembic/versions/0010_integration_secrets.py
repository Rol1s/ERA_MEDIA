"""integration secrets

Revision ID: 0010_integration_secrets
Revises: 0009_unschedule_nonpub
Create Date: 2026-04-30 18:05:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_integration_secrets"
down_revision: Union[str, None] = "0009_unschedule_nonpub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_secrets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("integration_id", sa.Integer(), sa.ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("secret_name", sa.String(length=120), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("masked_value", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="configured"),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_integration_secrets_integration_id", "integration_secrets", ["integration_id"])
    op.create_index("ix_integration_secrets_provider", "integration_secrets", ["provider"])
    op.create_index("ix_integration_secrets_secret_name", "integration_secrets", ["secret_name"])
    op.create_index("ix_integration_secrets_status", "integration_secrets", ["status"])
    op.create_unique_constraint("uq_integration_secret_provider_name", "integration_secrets", ["provider", "secret_name"])


def downgrade() -> None:
    op.drop_constraint("uq_integration_secret_provider_name", "integration_secrets", type_="unique")
    op.drop_index("ix_integration_secrets_status", table_name="integration_secrets")
    op.drop_index("ix_integration_secrets_secret_name", table_name="integration_secrets")
    op.drop_index("ix_integration_secrets_provider", table_name="integration_secrets")
    op.drop_index("ix_integration_secrets_integration_id", table_name="integration_secrets")
    op.drop_table("integration_secrets")
