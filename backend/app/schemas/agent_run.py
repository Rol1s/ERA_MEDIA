from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentRunCreate(BaseModel):
    agent_name: str
    task_type: str
    input_json: dict[str, Any] = Field(default_factory=dict)
    output_json: dict[str, Any] = Field(default_factory=dict)
    status: str
    error_message: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    estimated_cost: float = 0
    provider: str = "mock"
    model: str = "mock"
    prompt_template_id: int | None = None
    prompt_version: int | None = None


class AgentRunRead(AgentRunCreate):
    id: int
    started_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}
