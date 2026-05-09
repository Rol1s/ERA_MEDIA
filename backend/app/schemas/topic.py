from datetime import datetime

from pydantic import BaseModel, Field


class TopicBase(BaseModel):
    source_id: int | None = None
    source_item_id: int | None = None
    daily_edition_id: int | None = None
    title: str
    url: str | None = None
    raw_text: str = ""
    summary: str = ""
    published_at: datetime | None = None
    freshness_score: float = 0
    relevance_score: float = 0
    virality_score: float = 0
    usefulness_score: float = 0
    originality_score: float = 0
    importance_score: float = 0
    source_trust_score: float = 0
    risk_score: float = 0
    final_score: float = 0
    why_this_matters: str = ""
    suggested_angle: str = ""
    assigned_channel_ids: list[int] = Field(default_factory=list)
    is_duplicate: bool = False
    is_demo: bool = False
    duplicate_of_topic_id: int | None = None
    status: str = "new"
    extraction_status: str = ""
    extraction_error: str = ""
    content_length: int = 0
    language: str = ""
    source_published_at: datetime | None = None
    canonical_url: str = ""
    paywall_or_blocked_detected: bool = False


class TopicCreate(TopicBase):
    pass


class TopicUpdate(BaseModel):
    source_id: int | None = None
    source_item_id: int | None = None
    daily_edition_id: int | None = None
    title: str | None = None
    url: str | None = None
    raw_text: str | None = None
    summary: str | None = None
    published_at: datetime | None = None
    freshness_score: float | None = None
    relevance_score: float | None = None
    virality_score: float | None = None
    usefulness_score: float | None = None
    originality_score: float | None = None
    importance_score: float | None = None
    source_trust_score: float | None = None
    risk_score: float | None = None
    final_score: float | None = None
    why_this_matters: str | None = None
    suggested_angle: str | None = None
    assigned_channel_ids: list[int] | None = None
    is_duplicate: bool | None = None
    is_demo: bool | None = None
    duplicate_of_topic_id: int | None = None
    status: str | None = None
    extraction_status: str | None = None
    extraction_error: str | None = None
    content_length: int | None = None
    language: str | None = None
    source_published_at: datetime | None = None
    canonical_url: str | None = None
    paywall_or_blocked_detected: bool | None = None


class TopicRead(TopicBase):
    id: int
    detected_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
