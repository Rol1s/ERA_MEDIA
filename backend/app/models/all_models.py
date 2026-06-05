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
    channel_mode: Mapped[str] = mapped_column(String(40), default="newsroom", index=True)
    relay_mode: Mapped[str] = mapped_column(String(60), default="")
    relay_source_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    relay_publish_delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    relay_max_posts_per_day: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)

    posts: Mapped[list["Post"]] = relationship(back_populates="channel")
    source_maps: Mapped[list["SourceChannelMap"]] = relationship(back_populates="channel")


class ChannelVoiceProfile(Base, TimestampMixin):
    __tablename__ = "channel_voice_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), unique=True, index=True)
    voice_name: Mapped[str] = mapped_column(String(160), default="")
    audience: Mapped[str] = mapped_column(Text, default="")
    tone: Mapped[str] = mapped_column(Text, default="")
    allowed_opinion_level: Mapped[str] = mapped_column(String(40), default="light", index=True)
    style_rules_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    forbidden_phrases_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    structure_preferences_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    hook_rules_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    opinion_rules_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_rules_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    examples_good_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    examples_bad_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)


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
    source_priority: Mapped[str] = mapped_column(String(40), default="normal", index=True)
    source_quality_tier: Mapped[str] = mapped_column(String(60), default="reputable_media", index=True)
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    breaking_monitor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reliability_score: Mapped[float] = mapped_column(Float, default=0.7)
    speed_score: Mapped[float] = mapped_column(Float, default=0.5)
    noise_score: Mapped[float] = mapped_column(Float, default=0.2)
    ingestion_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    requires_operator_approval: Mapped[bool] = mapped_column(Boolean, default=True)

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
    normalized_url: Mapped[str] = mapped_column(Text, default="", index=True)
    external_id: Mapped[str] = mapped_column(String(500), default="", index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    normalized_title: Mapped[str] = mapped_column(String(500), default="", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_html_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    content_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extracted_summary: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    language: Mapped[str] = mapped_column(String(20), default="")
    content_length: Mapped[int] = mapped_column(Integer, default=0)
    extraction_status: Mapped[str] = mapped_column(String(40), default="fetched", index=True)
    extraction_error: Mapped[str] = mapped_column(Text, default="")
    paywall_or_blocked_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_item_id: Mapped[int | None] = mapped_column(ForeignKey("source_items.id"), nullable=True, index=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    age_minutes: Mapped[int] = mapped_column(Integer, default=0)
    content_age_minutes: Mapped[int] = mapped_column(Integer, default=0)
    detection_age_minutes: Mapped[int] = mapped_column(Integer, default=0)
    freshness_score: Mapped[float] = mapped_column(Float, default=0)
    source_priority: Mapped[str] = mapped_column(String(40), default="normal", index=True)
    is_breaking_candidate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_new_to_system: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_new_in_world: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    freshness_basis: Mapped[str] = mapped_column(String(60), default="unknown", index=True)
    content_type: Mapped[str] = mapped_column(String(60), default="unknown", index=True)
    freshness_reason: Mapped[str] = mapped_column(Text, default="")
    story_cluster_id: Mapped[str] = mapped_column(String(160), default="", index=True)
    dedup_decision_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    source: Mapped["Source"] = relationship(back_populates="items")
    topic: Mapped["Topic | None"] = relationship(back_populates="source_item", uselist=False)


class LlmCache(Base, TimestampMixin):
    __tablename__ = "llm_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(260), unique=True, index=True)
    source_item_id: Mapped[int | None] = mapped_column(ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True, index=True)
    pipeline_step: Mapped[str] = mapped_column(String(120), index=True)
    prompt_version: Mapped[str] = mapped_column(String(80), default="")
    input_hash: Mapped[str] = mapped_column(String(128), index=True)
    provider: Mapped[str] = mapped_column(String(60), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    response_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    tokens_saved_estimate: Mapped[int] = mapped_column(Integer, default=0)
    hits: Mapped[int] = mapped_column(Integer, default=0)


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
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canonical_url: Mapped[str] = mapped_column(Text, default="")
    paywall_or_blocked_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    urgency_score: Mapped[float] = mapped_column(Float, default=0)
    novelty_score: Mapped[float] = mapped_column(Float, default=0)
    dedup_decision_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    evidence_pack_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    recommended_post_type: Mapped[str] = mapped_column(String(40), default="NEWS", index=True)
    matched_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True, index=True)
    first_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_source_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(40), default="evergreen", index=True)
    freshness_reason: Mapped[str] = mapped_column(Text, default="")
    story_cluster_id: Mapped[str] = mapped_column(String(160), default="", index=True)
    content_age_minutes: Mapped[int] = mapped_column(Integer, default=0)
    detection_age_minutes: Mapped[int] = mapped_column(Integer, default=0)
    is_new_to_system: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_new_in_world: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    freshness_basis: Mapped[str] = mapped_column(String(60), default="unknown", index=True)
    content_type: Mapped[str] = mapped_column(String(60), default="unknown", index=True)

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
    visual_type: Mapped[str] = mapped_column(String(60), default="none", index=True)
    visual_safety_notes: Mapped[str] = mapped_column(Text, default="")
    image_generation_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    image_generation_status: Mapped[str] = mapped_column(String(60), default="not_requested", index=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_urls: Mapped[list[str]] = mapped_column(JSONB, default=list)
    post_type: Mapped[str] = mapped_column(String(40), default="NEWS", index=True)
    novelty_score: Mapped[float] = mapped_column(Float, default=0)
    dedup_decision_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    quality_verdict: Mapped[str] = mapped_column(String(60), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    status_reason: Mapped[str] = mapped_column(Text, default="")
    risk_reason: Mapped[str] = mapped_column(Text, default="")
    quality_reason: Mapped[str] = mapped_column(Text, default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_url: Mapped[str] = mapped_column(Text, default="")
    manual_publish_note: Mapped[str] = mapped_column(Text, default="")
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
    media_source_type: Mapped[str] = mapped_column(String(60), default="none", index=True)
    media_source_url: Mapped[str] = mapped_column(Text, default="")
    media_rights_note: Mapped[str] = mapped_column(Text, default="")
    media_status: Mapped[str] = mapped_column(String(60), default="missing", index=True)
    max_packaged_text: Mapped[str] = mapped_column(Text, default="")
    max_buttons_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    operator_checklist_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    channel: Mapped["Channel"] = relationship(back_populates="posts")
    topic: Mapped["Topic | None"] = relationship(back_populates="posts")
    daily_edition: Mapped["DailyEdition | None"] = relationship(back_populates="posts")
    metrics: Mapped[list["Metric"]] = relationship(back_populates="post")


class NewsroomSubmission(Base, TimestampMixin):
    __tablename__ = "newsroom_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(40), default="new", index=True)
    source: Mapped[str] = mapped_column(String(60), default="telegram", index=True)
    submitter_chat_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    submitter_name: Mapped[str] = mapped_column(String(240), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    media_url: Mapped[str] = mapped_column(Text, default="")
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    rejected_reason: Mapped[str] = mapped_column(Text, default="")


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
    skill_contract_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    task_contract_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    contract_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    contract_version: Mapped[str] = mapped_column(String(40), default="")
    schema_version: Mapped[str] = mapped_column(String(40), default="")
    skill_version: Mapped[str] = mapped_column(String(40), default="")
    prompt_template_version: Mapped[str] = mapped_column(String(40), default="")
    input_contract_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output_contract_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    handoff_contract_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    validation_result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    escalation_contract_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    raw_response_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    queue_wait_ms: Mapped[int] = mapped_column(Integer, default=0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    next_agent: Mapped[str] = mapped_column(String(120), default="")
    next_action: Mapped[str] = mapped_column(String(160), default="")
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
    task_contract_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output_contract_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    validation_result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    handoff_contract_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    escalation_contract_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    subscribers_before: Mapped[int] = mapped_column(Integer, default=0)
    subscribers_after: Mapped[int] = mapped_column(Integer, default=0)
    subscribers_delta: Mapped[int] = mapped_column(Integer, default=0)
    link_clicks: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["Post"] = relationship(back_populates="metrics")


class ArchivedGeneratedContent(Base, TimestampMixin):
    __tablename__ = "archived_generated_content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    generation_mode: Mapped[str] = mapped_column(String(40), default="", index=True)
    provider: Mapped[str] = mapped_column(String(80), default="", index=True)
    status: Mapped[str] = mapped_column(String(80), default="", index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    archive_reason: Mapped[str] = mapped_column(Text, default="")


class GrowthCampaign(Base, TimestampMixin):
    __tablename__ = "growth_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    target_channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True, index=True)
    goal: Mapped[str] = mapped_column(String(120), default="subscribers", index=True)
    offer: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(Text, default="")
    tone: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str] = mapped_column(String(40), default="controlled_gray", index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    hypothesis_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    kpi_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    target_channel: Mapped["Channel | None"] = relationship()
    assets: Mapped[list["FunnelAsset"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    seeding_runs: Mapped[list["SeedingRun"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class FunnelAsset(Base, TimestampMixin):
    __tablename__ = "funnel_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("growth_campaigns.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_type: Mapped[str] = mapped_column(String(60), index=True)
    platform: Mapped[str] = mapped_column(String(60), default="max", index=True)
    title: Mapped[str] = mapped_column(String(260), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    cta: Mapped[str] = mapped_column(Text, default="")
    target_url: Mapped[str] = mapped_column(Text, default="")
    risk_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    campaign: Mapped["GrowthCampaign"] = relationship(back_populates="assets")
    post: Mapped["Post | None"] = relationship()


class TrafficSource(Base, TimestampMixin):
    __tablename__ = "traffic_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(60), default="manual", index=True)
    category: Mapped[str] = mapped_column(String(80), default="comments", index=True)
    url: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str] = mapped_column(String(40), default="medium", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)


class SeedingRun(Base, TimestampMixin):
    __tablename__ = "seeding_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("growth_campaigns.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("funnel_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    traffic_source_id: Mapped[int | None] = mapped_column(ForeignKey("traffic_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(60), default="manual", index=True)
    placements_count: Mapped[int] = mapped_column(Integer, default=0)
    link_clicks: Mapped[int] = mapped_column(Integer, default=0)
    joins: Mapped[int] = mapped_column(Integer, default=0)
    bans: Mapped[int] = mapped_column(Integer, default=0)
    complaints: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    campaign: Mapped["GrowthCampaign"] = relationship(back_populates="seeding_runs")
    asset: Mapped["FunnelAsset | None"] = relationship()
    traffic_source: Mapped["TrafficSource | None"] = relationship()


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

    # Agent Dispatch & Control properties
    current_thought: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_topic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False)
    human_action_required: Mapped[str | None] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    daily_cost_cached: Mapped[float] = mapped_column(Float, default=0.0)
    daily_tokens_cached: Mapped[int] = mapped_column(Integer, default=0)

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


class EditorialDirectorSession(Base, TimestampMixin):
    __tablename__ = "editorial_director_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(240), default="", index=True)
    status: Mapped[str] = mapped_column(String(60), default="open", index=True)
    mode: Mapped[str] = mapped_column(String(60), default="operator_command", index=True)
    command: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    report_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_issue_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    requires_human_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)


class EditorialDirectorMessage(Base):
    __tablename__ = "editorial_director_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("editorial_director_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(40), default="assistant", index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


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


class AgentSkillContract(Base, TimestampMixin):
    __tablename__ = "agent_skill_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(140), index=True)
    mission: Mapped[str] = mapped_column(Text, default="")
    responsibilities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    allowed_actions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    forbidden_actions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    allowed_tools: Mapped[list[str]] = mapped_column(JSONB, default=list)
    forbidden_tools: Mapped[list[str]] = mapped_column(JSONB, default=list)
    success_criteria: Mapped[list[str]] = mapped_column(JSONB, default=list)
    failure_criteria: Mapped[list[str]] = mapped_column(JSONB, default=list)
    escalation_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    provider: Mapped[str] = mapped_column(String(80), default="ollama", index=True)
    model: Mapped[str] = mapped_column(String(160), default="gemma4:e4b")
    timeout: Mapped[int] = mapped_column(Integer, default=90)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    latency_limit: Mapped[int] = mapped_column(Integer, default=120000)
    owner: Mapped[str] = mapped_column(String(140), default="")
    reviewer: Mapped[str] = mapped_column(String(140), default="")
    contract_version: Mapped[str] = mapped_column(String(40), default="v1")
    skill_version: Mapped[str] = mapped_column(String(40), default="v1")
    schema_version: Mapped[str] = mapped_column(String(40), default="v1")
    prompt_template_version: Mapped[str] = mapped_column(String(40), default="v1")
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)


class ContractTemplate(Base, TimestampMixin):
    __tablename__ = "contract_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    contract_type: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    template_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    default_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    contract_version: Mapped[str] = mapped_column(String(40), default="v1")
    schema_version: Mapped[str] = mapped_column(String(40), default="v1")
    prompt_template_version: Mapped[str] = mapped_column(String(40), default="v1")
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)


class ContractVersion(Base, TimestampMixin):
    __tablename__ = "contract_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(40), default="v1", index=True)
    schema_version: Mapped[str] = mapped_column(String(40), default="v1")
    skill_version: Mapped[str] = mapped_column(String(40), default="")
    prompt_template_version: Mapped[str] = mapped_column(String(40), default="v1")
    template_id: Mapped[int | None] = mapped_column(ForeignKey("contract_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    skill_contract_id: Mapped[int | None] = mapped_column(ForeignKey("agent_skill_contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    template_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    change_note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)


class PromptTemplate(Base, TimestampMixin):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    agent_type: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    content: Mapped[str] = mapped_column(Text)
    variables_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
