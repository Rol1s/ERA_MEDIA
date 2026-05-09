from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import Source, SourceChannelMap, SourceItem, Topic
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate
from app.schemas.source_item import SourceItemRead
from app.services.org import log_activity
from app.services.source_ingestion import SourceFetchService

router = APIRouter()


def sync_source_channels(db: Session, source: Source, channel_ids: list[int]) -> None:
    db.execute(delete(SourceChannelMap).where(SourceChannelMap.source_id == source.id))
    for channel_id in channel_ids:
        db.add(SourceChannelMap(source_id=source.id, channel_id=channel_id, relevance_weight=1.0, enabled=True))


def source_payload(db: Session, source: Source) -> dict[str, Any]:
    channel_ids = list(
        db.execute(select(SourceChannelMap.channel_id).where(SourceChannelMap.source_id == source.id)).scalars()
    )
    item_count = db.scalar(select(func.count()).select_from(SourceItem).where(SourceItem.source_id == source.id)) or 0
    valid_count = db.scalar(select(func.count()).select_from(SourceItem).where(SourceItem.source_id == source.id, SourceItem.extraction_status == "extracted")) or 0
    duplicate_count = db.scalar(select(func.count()).select_from(SourceItem).where(SourceItem.source_id == source.id, SourceItem.extraction_status == "duplicate")) or 0
    failed_count = db.scalar(select(func.count()).select_from(SourceItem).where(SourceItem.source_id == source.id, SourceItem.extraction_status.in_(["failed", "too_short", "blocked"]))) or 0
    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "type": source.type,
        "language": source.language,
        "trust_score": source.trust_score,
        "check_interval_minutes": source.check_interval_minutes,
        "last_checked_at": source.last_checked_at,
        "requires_review": source.requires_review,
        "last_error": source.last_error,
        "health_status": source.health_status,
        "is_demo": source.is_demo,
        "status": source.status,
        "channel_ids": channel_ids,
        "items_count": item_count,
        "valid_items_count": valid_count,
        "duplicate_items_count": duplicate_count,
        "failed_items_count": failed_count,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


@router.get("", response_model=None)
def list_sources(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    sources = db.execute(select(Source).order_by(Source.id)).scalars().all()
    return [source_payload(db, source) for source in sources]


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    data = payload.model_dump(exclude={"channel_ids"})
    source = Source(**data)
    db.add(source)
    db.commit()
    db.refresh(source)
    if payload.channel_ids:
        sync_source_channels(db, source, payload.channel_ids)
        db.commit()
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="source_created",
        entity_type="source",
        entity_id=source.id,
        message=f"Source created: {source.name}",
    )
    db.commit()
    return source_payload(db, source)


@router.get("/{source_id}", response_model=None)
def get_source(source_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source_payload(db, source)


@router.patch("/{source_id}", response_model=None)
def update_source(source_id: int, payload: SourceUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    data = payload.model_dump(exclude_unset=True)
    channel_ids = data.pop("channel_ids", None)
    for key, value in data.items():
        setattr(source, key, value)
    if channel_ids is not None:
        sync_source_channels(db, source, channel_ids)
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="source_updated",
        entity_type="source",
        entity_id=source.id,
        message=f"Source updated: {source.name}",
    )
    db.commit()
    db.refresh(source)
    return source_payload(db, source)


@router.post("/{source_id}/health-check", response_model=None)
def health_check_source(source_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.url:
        raise HTTPException(status_code=422, detail="Source URL is empty")
    metadata = SourceFetchService().check_health(db, source)
    db.refresh(source)
    return {**source_payload(db, source), "health": metadata}


@router.post("/{source_id}/fetch", response_model=None)
def fetch_source(
    source_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.url:
        raise HTTPException(status_code=422, detail="Source URL is empty")
    result = SourceFetchService().fetch_source(db, source, limit=limit, create_topics=True)
    db.refresh(source)
    return {"source": source_payload(db, source), "result": result.as_dict()}


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


@router.get("/items", response_model=None)
def list_source_items(
    source_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(SourceItem).order_by(SourceItem.created_at.desc())
    if source_id:
        stmt = stmt.where(SourceItem.source_id == source_id)
    if status_filter:
        stmt = stmt.where(SourceItem.extraction_status == status_filter)
    return [source_item_payload(db, item) for item in db.execute(stmt.limit(200)).scalars().all()]


@router.get("/items/{item_id}", response_model=None)
def get_source_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(SourceItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Source item not found")
    return source_item_payload(db, item)


@router.post("/items/{item_id}/create-topic", response_model=None)
def create_topic_from_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(SourceItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Source item not found")
    if item.source is None:
        raise HTTPException(status_code=422, detail="Source item has no source")
    topic = SourceFetchService().topic_creator.create_or_update_topic(db, item.source, item)
    db.commit()
    if topic is None:
        raise HTTPException(status_code=422, detail="Duplicate item cannot create a new topic")
    return {"topic_id": topic.id, "topic_status": topic.status, "source_item": source_item_payload(db, item)}


@router.post("/items/{item_id}/reject", response_model=None)
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


@router.post("/items/{item_id}/refetch", response_model=None)
def refetch_source_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(SourceItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Source item not found")
    result = SourceFetchService().fetch_source(db, item.source, limit=5, create_topics=True)
    return {"result": result.as_dict()}


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, db: Session = Depends(get_db)) -> None:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="source_deleted",
        entity_type="source",
        entity_id=source.id,
        message=f"Source deleted: {source.name}",
        metadata={"is_demo": source.is_demo},
    )
    db.delete(source)
    db.commit()
