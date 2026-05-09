from datetime import datetime

from pydantic import BaseModel, Field


class ChannelBase(BaseModel):
    name: str
    slug: str
    platform: str = "max"
    category: str
    description: str = ""
    tone_of_voice: str = ""
    audience_description: str = ""
    topics_allowed: list[str] = Field(default_factory=list)
    topics_forbidden: list[str] = Field(default_factory=list)
    posting_frequency_per_day: int = 1
    daily_post_limit: int = 1
    publish_mode: str = "manual"
    auto_publish_enabled: bool = False
    risk_threshold: float = 0.5
    status: str = "active"


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    platform: str | None = None
    category: str | None = None
    description: str | None = None
    tone_of_voice: str | None = None
    audience_description: str | None = None
    topics_allowed: list[str] | None = None
    topics_forbidden: list[str] | None = None
    posting_frequency_per_day: int | None = None
    daily_post_limit: int | None = None
    publish_mode: str | None = None
    auto_publish_enabled: bool | None = None
    risk_threshold: float | None = None
    status: str | None = None


class ChannelRead(ChannelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
