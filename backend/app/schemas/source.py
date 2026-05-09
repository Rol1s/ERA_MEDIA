from datetime import datetime

from pydantic import BaseModel, Field


class SourceBase(BaseModel):
    name: str
    url: str
    type: str = "rss"
    language: str = "ru"
    trust_score: float = 0.7
    check_interval_minutes: int = 60
    last_checked_at: datetime | None = None
    requires_review: bool = True
    last_error: str = ""
    health_status: str = "unknown"
    is_demo: bool = False
    status: str = "active"


class SourceCreate(SourceBase):
    channel_ids: list[int] = Field(default_factory=list)


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    type: str | None = None
    language: str | None = None
    trust_score: float | None = None
    check_interval_minutes: int | None = None
    last_checked_at: datetime | None = None
    requires_review: bool | None = None
    last_error: str | None = None
    health_status: str | None = None
    is_demo: bool | None = None
    status: str | None = None
    channel_ids: list[int] | None = None


class SourceRead(SourceBase):
    id: int
    channel_ids: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
