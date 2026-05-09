from datetime import datetime

from pydantic import BaseModel, Field


class PostBase(BaseModel):
    channel_id: int
    topic_id: int | None = None
    daily_edition_id: int | None = None
    title: str
    body: str
    visual_prompt: str = ""
    visual_url: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    status: str = "draft"
    risk_score: float = 0
    quality_score: float = 0
    status_reason: str = ""
    risk_reason: str = ""
    quality_reason: str = ""
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    max_message_id: str | None = None
    created_by_agent: str = "editor_agent"
    approved_by: str | None = None
    version: int = 1
    version_history: list[dict] = Field(default_factory=list)
    is_demo: bool = False
    mock_only: bool = False
    not_publishable_reason: str = ""
    generation_mode: str = "mock"
    provider: str = "mock"
    model: str = "mock"
    prompt_template_version: int | None = None
    publishable: bool = False
    non_publishable_reason: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    estimated_cost_usd: float = 0
    llm_trace_id: str | None = None
    structured_outputs_json: dict = Field(default_factory=dict)


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    channel_id: int | None = None
    topic_id: int | None = None
    daily_edition_id: int | None = None
    title: str | None = None
    body: str | None = None
    visual_prompt: str | None = None
    visual_url: str | None = None
    source_urls: list[str] | None = None
    status: str | None = None
    risk_score: float | None = None
    quality_score: float | None = None
    status_reason: str | None = None
    risk_reason: str | None = None
    quality_reason: str | None = None
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    max_message_id: str | None = None
    created_by_agent: str | None = None
    approved_by: str | None = None
    version: int | None = None
    version_history: list[dict] | None = None
    is_demo: bool | None = None
    mock_only: bool | None = None
    not_publishable_reason: str | None = None
    generation_mode: str | None = None
    provider: str | None = None
    model: str | None = None
    prompt_template_version: int | None = None
    publishable: bool | None = None
    non_publishable_reason: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    estimated_cost_usd: float | None = None
    llm_trace_id: str | None = None
    structured_outputs_json: dict | None = None


class PostRead(PostBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
