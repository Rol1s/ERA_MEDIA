from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import SourceItem, Topic
from app.services.org import log_activity
from app.services.source_ingestion import SourceFetchService

router = APIRouter()


def source_item_payload(db: Session, item: SourceItem) -> dict[str, Any]:
    topic_id = db.scalar(select(Topic.id).where(Topic.source_item_id == item.id))
    return {
        "id": item.id,
        "source_id": item.source_id,
        "url": item.url,
        "canonical_url": item.canonical_url,
        "title": item.title,
        "summary": item.summary,
        "extracted_text": item.extracted_text,
        "extracted_summary": item.extracted_summary,
        "published_at": item.published_at,
        "detected_at": item.detected_at,
        "language": item.language,
        "content_length": item.content_length,
        "extraction_status": item.extraction_status,
        "extraction_error": item.extraction_error,
        "paywall_or_blocked_detected": item.paywall_or_blocked_detected,
        "duplicate_of_item_id": item.duplicate_of_item_id,
        "linked_topic_id": topic_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("", response_model=None)
def list_source_items(
    source_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    language: str | None = None,
    duplicate: bool | None = None,
    blocked: bool | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(SourceItem).order_by(SourceItem.created_at.desc())
    if source_id:
        stmt = stmt.where(SourceItem.source_id == source_id)
    if status_filter:
        stmt = stmt.where(SourceItem.extraction_status == status_filter)
    if language:
        stmt = stmt.where(SourceItem.language == language)
    if duplicate is not None:
        stmt = stmt.where(SourceItem.duplicate_of_item_id.is_not(None) if duplicate else SourceItem.duplicate_of_item_id.is_(None))
    if blocked is not None:
        stmt = stmt.where(SourceItem.paywall_or_blocked_detected.is_(blocked))
    return [source_item_payload(db, item) for item in db.execute(stmt.limit(200)).scalars().all()]


@router.get("/{item_id}", response_model=None)
def get_source_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(SourceItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Source item not found")
    return source_item_payload(db, item)


@router.post("/{item_id}/create-topic", response_model=None)
def create_topic_from_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(SourceItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Source item not found")
    topic = SourceFetchService().topic_creator.create_or_update_topic(db, item.source, item)
    db.commit()
    if topic is None:
        raise HTTPException(status_code=422, detail="Duplicate item cannot create a new topic")
    return {"topic_id": topic.id, "topic_status": topic.status, "source_item": source_item_payload(db, item)}


@router.post("/{item_id}/reject", response_model=None)
def reject_source_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(SourceItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Source item not found")
    item.extraction_status = "rejected"
    item.extraction_error = "Rejected by human operator"
    log_activity(db, actor_type="human", actor_id=None, event_type="source_item_rejected", entity_type="source_item", entity_id=item.id, message=f"Source item rejected: {item.title}")
    db.commit()
    db.refresh(item)
    return source_item_payload(db, item)


@router.post("/{item_id}/refetch", response_model=None)
def refetch_source_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(SourceItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Source item not found")
    result = SourceFetchService().fetch_source(db, item.source, limit=5, create_topics=True)
    return {"result": result.as_dict()}
