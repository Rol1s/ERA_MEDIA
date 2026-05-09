from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    task_type: str
    payload_json: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    attempts: int = 0
    max_attempts: int = 1
    error_message: str | None = None
    idempotency_key: str | None = None


class TaskUpdate(BaseModel):
    task_type: str | None = None
    payload_json: dict[str, Any] | None = None
    status: str | None = None
    attempts: int | None = None
    max_attempts: int | None = None
    locked_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    idempotency_key: str | None = None


class TaskRead(TaskCreate):
    id: int
    locked_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

