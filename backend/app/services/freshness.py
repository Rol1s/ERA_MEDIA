"""Freshness scoring helpers.

Local fallback implementation for the MAX publication package.  The original
Codex package referenced this module but did not include it; keep the logic
simple and deterministic so source ingestion and channel workspaces can run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import Source, SourceItem, Topic


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_minutes(dt: datetime | None) -> int:
    if dt is None:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, int((_now() - dt).total_seconds() // 60))


def _score_from_age(minutes: int) -> float:
    if minutes <= 60:
        return 1.0
    if minutes <= 6 * 60:
        return 0.8
    if minutes <= 24 * 60:
        return 0.55
    if minutes <= 72 * 60:
        return 0.25
    return 0.05


def score_source_item(item: SourceItem, source: Source | None = None) -> SourceItem:
    published = getattr(item, "published_at", None) or getattr(item, "source_updated_at", None) or getattr(item, "created_at", None)
    age = _age_minutes(published)
    detection_age = _age_minutes(getattr(item, "first_seen_at", None) or getattr(item, "created_at", None))
    item.age_minutes = age
    item.content_age_minutes = age
    item.detection_age_minutes = detection_age
    item.freshness_score = _score_from_age(age)
    item.is_stale = age > 72 * 60
    item.is_new_to_system = detection_age <= 24 * 60
    item.is_new_in_world = age <= 24 * 60
    item.freshness_basis = "published_at" if getattr(item, "published_at", None) else "created_at"
    item.content_type = getattr(item, "content_type", None) or "article"
    item.freshness_reason = f"age={age}m; source={getattr(source, 'name', '') if source else ''}"
    if source is not None:
        item.source_priority = getattr(source, "source_priority", None) or "normal"
    return item


def score_topic(topic: Topic) -> Topic:
    published = getattr(topic, "source_updated_at", None) or getattr(topic, "created_at", None)
    age = _age_minutes(published)
    topic.content_age_minutes = age
    topic.detection_age_minutes = _age_minutes(getattr(topic, "first_detected_at", None) or getattr(topic, "created_at", None))
    topic.urgency_score = _score_from_age(age)
    topic.novelty_score = getattr(topic, "novelty_score", None) or 0.5
    topic.freshness_status = "fresh" if age <= 24 * 60 else ("stale" if age > 72 * 60 else "aging")
    topic.freshness_reason = f"age={age}m"
    topic.is_new_to_system = topic.detection_age_minutes <= 24 * 60
    topic.is_new_in_world = age <= 24 * 60
    topic.freshness_basis = "source_updated_at" if getattr(topic, "source_updated_at", None) else "created_at"
    topic.content_type = getattr(topic, "content_type", None) or "article"
    return topic


def refresh_freshness(db: Session, limit: int = 300) -> dict[str, Any]:
    items = list(db.execute(select(SourceItem).order_by(SourceItem.id.desc()).limit(limit)).scalars())
    topics = list(db.execute(select(Topic).order_by(Topic.id.desc()).limit(limit)).scalars())
    for item in items:
        score_source_item(item)
    for topic in topics:
        score_topic(topic)
    db.flush()
    return {"source_items": len(items), "topics": len(topics)}
