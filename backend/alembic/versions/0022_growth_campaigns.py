"""growth campaigns and seeding packs

Revision ID: 0022_growth_campaigns
Revises: 0021_cost_optimizer_relays
Create Date: 2026-06-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0022_growth_campaigns"
down_revision: str | None = "0021_cost_optimizer_relays"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "growth_campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("target_channel_id", sa.Integer(), nullable=True),
        sa.Column("goal", sa.String(length=120), nullable=False, server_default="subscribers"),
        sa.Column("offer", sa.Text(), nullable=False, server_default=""),
        sa.Column("audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("tone", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(length=40), nullable=False, server_default="controlled_gray"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("hypothesis_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("kpi_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["target_channel_id"], ["channels.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_growth_campaigns_name"), "growth_campaigns", ["name"], unique=True)
    op.create_index(op.f("ix_growth_campaigns_target_channel_id"), "growth_campaigns", ["target_channel_id"], unique=False)
    op.create_index(op.f("ix_growth_campaigns_goal"), "growth_campaigns", ["goal"], unique=False)
    op.create_index(op.f("ix_growth_campaigns_risk_level"), "growth_campaigns", ["risk_level"], unique=False)
    op.create_index(op.f("ix_growth_campaigns_status"), "growth_campaigns", ["status"], unique=False)

    op.create_table(
        "traffic_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("platform", sa.String(length=60), nullable=False, server_default="manual"),
        sa.Column("category", sa.String(length=80), nullable=False, server_default="comments"),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_traffic_sources_name"), "traffic_sources", ["name"], unique=True)
    op.create_index(op.f("ix_traffic_sources_platform"), "traffic_sources", ["platform"], unique=False)
    op.create_index(op.f("ix_traffic_sources_category"), "traffic_sources", ["category"], unique=False)
    op.create_index(op.f("ix_traffic_sources_risk_level"), "traffic_sources", ["risk_level"], unique=False)
    op.create_index(op.f("ix_traffic_sources_status"), "traffic_sources", ["status"], unique=False)

    op.create_table(
        "funnel_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=True),
        sa.Column("asset_type", sa.String(length=60), nullable=False),
        sa.Column("platform", sa.String(length=60), nullable=False, server_default="max"),
        sa.Column("title", sa.String(length=260), nullable=False, server_default=""),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("cta", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["campaign_id"], ["growth_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_funnel_assets_campaign_id"), "funnel_assets", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_funnel_assets_post_id"), "funnel_assets", ["post_id"], unique=False)
    op.create_index(op.f("ix_funnel_assets_asset_type"), "funnel_assets", ["asset_type"], unique=False)
    op.create_index(op.f("ix_funnel_assets_platform"), "funnel_assets", ["platform"], unique=False)
    op.create_index(op.f("ix_funnel_assets_status"), "funnel_assets", ["status"], unique=False)

    op.create_table(
        "seeding_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("traffic_source_id", sa.Integer(), nullable=True),
        sa.Column("platform", sa.String(length=60), nullable=False, server_default="manual"),
        sa.Column("placements_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("link_clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("joins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bans", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("complaints", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", sa.String(length=40), nullable=False, server_default="unknown"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["campaign_id"], ["growth_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["funnel_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["traffic_source_id"], ["traffic_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_seeding_runs_campaign_id"), "seeding_runs", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_seeding_runs_asset_id"), "seeding_runs", ["asset_id"], unique=False)
    op.create_index(op.f("ix_seeding_runs_traffic_source_id"), "seeding_runs", ["traffic_source_id"], unique=False)
    op.create_index(op.f("ix_seeding_runs_platform"), "seeding_runs", ["platform"], unique=False)
    op.create_index(op.f("ix_seeding_runs_result"), "seeding_runs", ["result"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_seeding_runs_result"), table_name="seeding_runs")
    op.drop_index(op.f("ix_seeding_runs_platform"), table_name="seeding_runs")
    op.drop_index(op.f("ix_seeding_runs_traffic_source_id"), table_name="seeding_runs")
    op.drop_index(op.f("ix_seeding_runs_asset_id"), table_name="seeding_runs")
    op.drop_index(op.f("ix_seeding_runs_campaign_id"), table_name="seeding_runs")
    op.drop_table("seeding_runs")
    op.drop_index(op.f("ix_funnel_assets_status"), table_name="funnel_assets")
    op.drop_index(op.f("ix_funnel_assets_platform"), table_name="funnel_assets")
    op.drop_index(op.f("ix_funnel_assets_asset_type"), table_name="funnel_assets")
    op.drop_index(op.f("ix_funnel_assets_post_id"), table_name="funnel_assets")
    op.drop_index(op.f("ix_funnel_assets_campaign_id"), table_name="funnel_assets")
    op.drop_table("funnel_assets")
    op.drop_index(op.f("ix_traffic_sources_status"), table_name="traffic_sources")
    op.drop_index(op.f("ix_traffic_sources_risk_level"), table_name="traffic_sources")
    op.drop_index(op.f("ix_traffic_sources_category"), table_name="traffic_sources")
    op.drop_index(op.f("ix_traffic_sources_platform"), table_name="traffic_sources")
    op.drop_index(op.f("ix_traffic_sources_name"), table_name="traffic_sources")
    op.drop_table("traffic_sources")
    op.drop_index(op.f("ix_growth_campaigns_status"), table_name="growth_campaigns")
    op.drop_index(op.f("ix_growth_campaigns_risk_level"), table_name="growth_campaigns")
    op.drop_index(op.f("ix_growth_campaigns_goal"), table_name="growth_campaigns")
    op.drop_index(op.f("ix_growth_campaigns_target_channel_id"), table_name="growth_campaigns")
    op.drop_index(op.f("ix_growth_campaigns_name"), table_name="growth_campaigns")
    op.drop_table("growth_campaigns")
