from datetime import datetime

from pydantic import BaseModel


class SourceItemRead(BaseModel):
    id: int
    source_id: int
    url: str
    canonical_url: str
    title: str
    summary: str
    extracted_text: str
    extracted_summary: str
    published_at: datetime | None
    detected_at: datetime
    language: str
    content_length: int
    extraction_status: str
    extraction_error: str
    paywall_or_blocked_detected: bool
    duplicate_of_item_id: int | None
    linked_topic_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
