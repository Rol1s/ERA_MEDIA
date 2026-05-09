from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(60), default="max")
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    tone_of_voice: Mapped[str] = mapped_column(Text, default="")
    audience_description: Mapped[str] = mapped_column(Text, default="")
    topics_allowed: Mapped[list[str]] = mapped_column(JSONB, default=list)
    topics_forbidden: Mapped[list[str]] = mapped_column(JSONB, default=list)
    posting_frequency_per_day: Mapped[int] = mapped_column(Integer, default=1)
    daily_post_limit: Mapped[int] = mapped_column(Integer, default=1)
    publish_mode: Mapped[str] = mapped_column(String(40), default="manual")
    auto_publish_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_threshold: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)

    posts: Mapped[list["Post"]] = relationship(back_populates="channel")
    source_maps: Mapped[list["SourceChannelMap"]] = relationship(back_populates="channel")


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    url: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(40), default="rss")
    language: Mapped[str] = mapped_column(String(20), default="ru")
    trust_score: Mapped[float] = mapped_column(Float, default=0.7)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    health_status: Mapped[str] = mapped_column(String(40), default="unknown")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)

    topics: Mapped[list["Topic"]] = relationship(back_populates="source")
    items: Mapped[list["SourceItem"]] = relationship(back_populates="source")
    channel_maps: Mapped[list["SourceChannelMap"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SourceChannelMap(Base):
    __tablename__ = "source_channel_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    relevance_weight: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    source: Mapped["Source"] = relationship(back_populates="channel_maps")
    channel: Mapped["Channel"] = relationship(back_populates="source_maps")


class SourceItem(Base, TimestampMixin):
    __tablename__ = "source_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text, index=True)
    canonical_url: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_html_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extracted_summary: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    language: Mapped[str] = mapped_column(String(20), default="")
    content_length: Mapped[int] = mapped_column(Integer, default=0)
    extraction_status: Mapped[str] = mapped_column(String(40), default="fetched", index=True)
    extraction_error: Mapped[str] = mapped_column(Text, default="")
    paywall_or_blocked_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_item_id: Mapped[int | None] = mapped_column(ForeignKey("source_items.id"), nullable=True, index=True)

    source: Mapped["Source"] = relationship(back_populates="items")
    topic: Mapped["Topic | None"] = relationship(back_populates="source_item", uselist=False)


class DailyEdition(Base, TimestampMixin):
    __tablename__ = "daily_editions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="collecting", index=True)
    target_topics_count: Mapped[int] = mapped_column(Integer, default=10)
    target_posts_count: Mapped[int] = mapped_column(Integer, default=5)
    selected_topics_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_posts_count: Mapped[int] = mapped_column(Integer, default=0)
    approved_posts_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_posts_count: Mapped[int] = mapped_column(Integer, default=0)
    editor_notes: Mapped[str] = mapped_column(Text, default="")

    channel: Mapped["Channel"] = relationship()
    topics: Mapped[list["Topic"]] = relationship(back_populates="daily_edition")
    posts: Mapped[list["Post"]] = relationship(back_populates="daily_edition")


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    source_item_id: Mapped[int | None] = mapped_column(ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True, index=True)
    daily_edition_id: Mapped[int | None] = mapped_column(ForeignKey("daily_editions.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    freshness_score: Mapped[float] = mapped_column(Float, default=0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0)
    virality_score: Mapped[float] = mapped_column(Float, default=0)
    usefulness_score: Mapped[float] = mapped_column(Float, default=0)
    originality_score: Mapped[float] = mapped_column(Float, default=0)
    importance_score: Mapped[float] = mapped_column(Float, default=0)
    source_trust_score: Mapped[float] = mapped_column(Float, default=0)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    final_score: Mapped[float] = mapped_column(Float, default=0)
    why_this_matters: Mapped[str] = mapped_column(Text, default="")
    suggested_angle: Mapped[str] = mapped_column(Text, default="")
    assigned_channel_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="new", index=True)
    extraction_status: Mapped[str] = mapped_column(String(40), default="")
    extraction_error: Mapped[str] = mapped_column(Text, default="")
    content_length: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(20), default="")
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canonical_url: Mapped[str] = mapped_column(Text, default="")
    paywall_or_blocked_detected: Mapped[bool] = mapped_column(Boolean, default=False)

    source: Mapped["Source | None"] = relationship(back_populates="topics")
    source_item: Mapped["SourceItem | None"] = relationship(back_populates="topic")
    daily_edition: Mapped["DailyEdition | None"] = relationship(back_populates="topics")
    posts: Mapped[list["Post"]] = relationship(back_populates="topic")


class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    daily_edition_id: Mapped[int | None] = mapped_column(ForeignKey("daily_editions.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    visual_prompt: Mapped[str] = mapped_column(Text, default="")
    visual_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_urls: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    status_reason: Mapped[str] = mapped_column(Text, default="")
    risk_reason: Mapped[str] = mapped_column(Text, default="")
    quality_reason: Mapped[str] = mapped_column(Text, default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_agent: Mapped[str] = mapped_column(String(120), default="editor_agent")
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    version_history: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    mock_only: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    not_publishable_reason: Mapped[str] = mapped_column(Text, default="")
    generation_mode: Mapped[str] = mapped_column(String(40), default="mock", index=True)
    provider: Mapped[str] = mapped_column(String(80), default="mock")
    model: Mapped[str] = mapped_column(String(160), default="mock")
    prompt_template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publishable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    non_publishable_reason: Mapped[str] = mapped_column(Text, default="")
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    llm_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    structured_outputs_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    channel: Mapped["Channel"] = relationship(back_populates="posts")
    topic: Mapped["Topic | None"] = relationship(back_populates="posts")
    daily_edition: Mapped["DailyEdition | None"] = relationship(back_populates="posts")
    metrics: Mapped[list["Metric"]] = relationship(back_populates="post")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(120), index=True)
    task_type: Mapped[str] = mapped_column(String(120), index=True)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(40), index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    provider: Mapped[str] = mapped_column(String(80), default="mock")
    model: Mapped[str] = mapped_column(String(160), default="mock")
    prompt_template_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(120), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(250), nullable=True, unique=True, index=True)


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    subscribers_delta: Mapped[int] = mapped_column(Integer, default=0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["Post"] = relationship(back_populates="metrics")


class OrgAgent(Base, TimestampMixin):
    __tablename__ = "org_agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    role: Mapped[str] = mapped_column(String(120), index=True)
    agent_type: Mapped[str] = mapped_column(String(80), default="agent")
    parent_agent_id: Mapped[int | None] = mapped_column(ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    responsibilities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    supervises: Mapped[list[str]] = mapped_column(JSONB, default=list)
    reviewed_by: Mapped[str] = mapped_column(String(140), default="")
    can_create_tasks: Mapped[bool] = mapped_column(Boolean, default=False)
    can_approve_posts: Mapped[bool] = mapped_column(Boolean, default=False)
    can_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    can_spend_budget: Mapped[bool] = mapped_column(Boolean, default=False)
    permissions_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    budget_daily: Mapped[float] = mapped_column(Float, default=0)
    budget_monthly: Mapped[float] = mapped_column(Float, default=0)
    token_limit_daily: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    heartbeat_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    heartbeat_cron: Mapped[str] = mapped_column(String(120), default="")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    parent: Mapped["OrgAgent | None"] = relationship(remote_side="OrgAgent.id")


class Goal(Base, TimestampMixin):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_agent_id: Mapped[int | None] = mapped_column(ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True)
    target_metric: Mapped[str] = mapped_column(String(120), default="")
    target_value: Mapped[float] = mapped_column(Float, default=0)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)


class Routine(Base, TimestampMixin):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_agent_id: Mapped[int | None] = mapped_column(ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True)
    cron_schedule: Mapped[str] = mapped_column(String(120), default="")
    task_type: Mapped[str] = mapped_column(String(120), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_runs_per_day: Mapped[int] = mapped_column(Integer, default=1)
    max_budget_per_run: Mapped[float] = mapped_column(Float, default=0)
    last_run_status: Mapped[str] = mapped_column(String(80), default="never")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CostEvent(Base):
    __tablename__ = "cost_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True, index=True)
    task_type: Mapped[str] = mapped_column(String(120), default="unknown", index=True)
    provider: Mapped[str] = mapped_column(String(80), default="mock")
    model: Mapped[str] = mapped_column(String(120), default="mock")
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(80), index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Integration(Base, TimestampMixin):
    __tablename__ = "integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="not_configured", index=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    secret_ref: Mapped[str] = mapped_column(String(240), default="")
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")


class IntegrationSecret(Base, TimestampMixin):
    __tablename__ = "integration_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_id: Mapped[int | None] = mapped_column(ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    secret_name: Mapped[str] = mapped_column(String(120), index=True)
    encrypted_value: Mapped[str] = mapped_column(Text)
    masked_value: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(40), default="configured", index=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlatformChannel(Base, TimestampMixin):
    __tablename__ = "platform_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(80), default="max", index=True)
    external_chat_id: Mapped[str] = mapped_column(String(240), default="")
    external_channel_url: Mapped[str] = mapped_column(Text, default="")
    integration_id: Mapped[int | None] = mapped_column(ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="not_connected", index=True)
    publish_mode: Mapped[str] = mapped_column(String(60), default="manual_copy")
    can_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    severity: Mapped[str] = mapped_column(String(40), default="info", index=True)
    title: Mapped[str] = mapped_column(String(240))
    message: Mapped[str] = mapped_column(Text, default="")
    entity_type: Mapped[str] = mapped_column(String(80), default="", index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="unread", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Issue(Base, TimestampMixin):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True)
    root_issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True)
    delegation_level: Mapped[int] = mapped_column(Integer, default=0)
    blocked_by_issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(260), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    issue_type: Mapped[str] = mapped_column(String(80), index=True)
    owner_agent_id: Mapped[int | None] = mapped_column(ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewer_agent_id: Mapped[int | None] = mapped_column(ForeignKey("org_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    related_channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True, index=True)
    related_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    related_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(40), default="normal", index=True)
    status: Mapped[str] = mapped_column(String(60), default="backlog", index=True)
    next_action: Mapped[str] = mapped_column(Text, default="")
    blocked_reason: Mapped[str] = mapped_column(Text, default="")
    required_human_action: Mapped[str] = mapped_column(Text, default="")
    target_metric: Mapped[str] = mapped_column(String(120), default="")
    target_value: Mapped[float] = mapped_column(Float, default=0)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    progress_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(260), nullable=True, unique=True, index=True)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OperatingLoopRun(Base):
    __tablename__ = "operating_loop_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String(60), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    planning_only: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    status: Mapped[str] = mapped_column(String(60), default="running", index=True)
    report_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    issues_created: Mapped[int] = mapped_column(Integer, default=0)
    issues_updated: Mapped[int] = mapped_column(Integer, default=0)
    issues_moved: Mapped[int] = mapped_column(Integer, default=0)
    decisions_made: Mapped[int] = mapped_column(Integer, default=0)
    warnings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    decision: Mapped[str] = mapped_column(String(120), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    alternatives_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class LLMModel(Base, TimestampMixin):
    __tablename__ = "llm_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(160), index=True)
    label: Mapped[str] = mapped_column(String(220))
    input_cost_per_1m: Mapped[float] = mapped_column(Float, default=0)
    output_cost_per_1m: Mapped[float] = mapped_column(Float, default=0)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_json_schema: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentConfig(Base, TimestampMixin):
    __tablename__ = "agent_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_agent_id: Mapped[int] = mapped_column(ForeignKey("org_agents.id", ondelete="CASCADE"), unique=True, index=True)
    prompt_template_id: Mapped[int | None] = mapped_column(ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), default="mock", index=True)
    model: Mapped[str] = mapped_column(String(160), default="mock")
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    max_tokens: Mapped[int] = mapped_column(Integer, default=800)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    tools_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    daily_budget_usd: Mapped[float] = mapped_column(Float, default=0)
    daily_token_limit: Mapped[int] = mapped_column(Integer, default=0)
    max_runs_per_day: Mapped[int] = mapped_column(Integer, default=1)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class PromptTemplate(Base, TimestampMixin):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    agent_type: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    content: Mapped[str] = mapped_column(Text)
    variables_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
