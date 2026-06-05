from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import ActivityEvent, Channel, PlatformChannel, Post, Source, SourceChannelMap, SourceItem, Topic
from app.schemas.channel import ChannelCreate, ChannelRead, ChannelUpdate
from app.services.freshness import refresh_freshness, score_topic
from app.services.org import log_activity
from app.services.source_ingestion import SourceFetchService

router = APIRouter()


class ChannelUrlIngestRequest(BaseModel):
    url: str
    title: str | None = None


@router.get("", response_model=list[ChannelRead])
def list_channels(db: Session = Depends(get_db)) -> list[Channel]:
    return list(db.execute(select(Channel).order_by(Channel.id)).scalars())


def _platform_payload(item: PlatformChannel | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "id": item.id,
        "channel_id": item.channel_id,
        "platform": item.platform,
        "external_chat_id": item.external_chat_id,
        "external_channel_url": item.external_channel_url,
        "integration_id": item.integration_id,
        "status": item.status,
        "publish_mode": item.publish_mode,
        "can_publish": item.can_publish,
        "last_test_at": item.last_test_at,
        "last_success_at": item.last_success_at,
        "last_error": item.last_error,
    }


def _topic_payload(topic: Topic) -> dict[str, Any]:
    return {
        "id": topic.id,
        "title": topic.title,
        "url": topic.canonical_url or topic.url,
        "source_id": topic.source_id,
        "source": topic.source.name if topic.source else "",
        "status": topic.status,
        "freshness_status": topic.freshness_status,
        "freshness_score": topic.freshness_score,
        "urgency_score": topic.urgency_score,
        "final_score": topic.final_score,
        "why_this_matters": topic.why_this_matters,
        "suggested_angle": topic.suggested_angle,
        "assigned_channel_ids": topic.assigned_channel_ids or [],
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
    }


def _post_payload(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "channel_id": post.channel_id,
        "topic_id": post.topic_id,
        "title": post.title,
        "body": post.body,
        "status": post.status,
        "risk_score": post.risk_score,
        "quality_score": post.quality_score,
        "source_urls": post.source_urls,
        "provider": post.provider,
        "model": post.model,
        "max_message_id": post.max_message_id,
        "max_packaged_text": post.max_packaged_text,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "published_at": post.published_at,
    }


def _source_payload(source: Source) -> dict[str, Any]:
    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "type": source.type,
        "language": source.language,
        "status": source.status,
        "health_status": source.health_status,
        "last_checked_at": source.last_checked_at,
        "last_error": source.last_error,
        "trust_score": source.trust_score,
        "reliability_score": source.reliability_score,
        "speed_score": source.speed_score,
        "noise_score": source.noise_score,
        "source_priority": source.source_priority,
        "source_quality_tier": source.source_quality_tier,
        "ingestion_enabled": source.ingestion_enabled,
        "items_count": len(source.items or []),
    }


def _source_score_for_channel(source: Source, channel: Channel) -> float:
    score = float(source.reliability_score or source.trust_score or 0.5) * 50
    score += float(source.trust_score or 0.5) * 25
    score += float(source.speed_score or 0.5) * 15
    score -= float(source.noise_score or 0) * 15
    if source.status == "active" and source.ingestion_enabled:
        score += 10
    if source.source_priority in {"breaking", "high", "priority"}:
        score += 8
    if source.source_quality_tier in {"primary", "official", "reputable_media"}:
        score += 8
    category_text = " ".join(
        [
            channel.category or "",
            channel.description or "",
            " ".join(channel.topics_allowed or []),
            source.name or "",
            source.url or "",
        ]
    ).lower()
    if channel.category and channel.category.lower() in category_text:
        score += 12
    if channel.category in {"food", "food_health"} and any(marker in category_text for marker in ["food", "еда", "health", "здоров", "bonappetit", "eater"]):
        score += 20
    if channel.category in {"news", "world", "politics"} and any(marker in category_text for marker in ["news", "tass", "ria", "reuters", "apnews", "bbc"]):
        score += 10
    return round(max(0, min(score, 100)), 2)


def _source_coverage(db: Session, channel: Channel, sources: list[Source]) -> dict[str, Any]:
    active_sources = [source for source in sources if source.status == "active" and source.ingestion_enabled]
    failed_sources = [source for source in sources if source.health_status == "failed" or bool(source.last_error)]
    total_items_today = 0
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    for source in sources:
        total_items_today += int(
            db.scalar(select(func.count()).select_from(SourceItem).where(SourceItem.source_id == source.id, SourceItem.created_at >= today)) or 0
        )
    if not sources:
        status = "empty"
        recommendation = "У канала нет источников. Привяжи источники из каталога, иначе радар будет пустым."
    elif len(active_sources) < 5:
        status = "thin"
        recommendation = "Источников мало. Добавь еще несколько активных источников под нишу канала."
    elif failed_sources:
        status = "degraded"
        recommendation = "Часть источников падает. Проверь health или замени их."
    else:
        status = "ok"
        recommendation = "Покрытие канала рабочее: можно обновлять радар и выбирать темы."
    return {
        "status": status,
        "recommendation": recommendation,
        "total_sources": len(sources),
        "active_sources": len(active_sources),
        "failed_sources": len(failed_sources),
        "items_today": total_items_today,
        "category": channel.category,
    }


def _suggested_sources(db: Session, channel: Channel, attached_source_ids: set[int], limit: int = 12) -> list[dict[str, Any]]:
    candidates = list(
        db.execute(
            select(Source)
            .where(
                Source.status == "active",
                Source.ingestion_enabled.is_(True),
                Source.is_demo.is_(False),
                Source.url != "",
                ~Source.url.ilike("%example.com%"),
                ~Source.name.ilike("%smoke%"),
                ~Source.name.ilike("%browser audit%"),
            )
            .order_by(Source.reliability_score.desc(), Source.trust_score.desc(), Source.id)
            .limit(300)
        ).scalars()
    )
    scored = []
    for source in candidates:
        if source.id in attached_source_ids:
            continue
        score = _source_score_for_channel(source, channel)
        reason = "подходит по качеству и активности источника"
        source_text = f"{source.name} {source.url}".lower()
        if channel.category and channel.category.lower() in source_text:
            reason = "совпадает с категорией канала"
        elif source.source_quality_tier in {"primary", "official"}:
            reason = "сильный первичный/официальный источник"
        elif source.reliability_score >= 0.75 or source.trust_score >= 0.75:
            reason = "высокое доверие к источнику"
        scored.append({"source": _source_payload(source), "fit_score": score, "reason": reason})
    scored.sort(key=lambda item: item["fit_score"], reverse=True)
    return scored[:limit]


@router.get("/{channel_id}/workspace", response_model=None)
def channel_workspace(channel_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    refresh_freshness(db, limit=300)
    platform = db.execute(
        select(PlatformChannel).where(PlatformChannel.channel_id == channel.id, PlatformChannel.platform == "max")
    ).scalar_one_or_none()
    sources = list(
        db.execute(
            select(Source)
            .join(SourceChannelMap, SourceChannelMap.source_id == Source.id)
            .where(SourceChannelMap.channel_id == channel.id, SourceChannelMap.enabled.is_(True), Source.is_demo.is_(False))
            .order_by(Source.status, Source.reliability_score.desc(), Source.trust_score.desc(), Source.id)
            .limit(100)
        ).scalars()
    )
    attached_source_ids = {source.id for source in sources}
    topics = list(
        db.execute(
            select(Topic)
            .where(
                Topic.assigned_channel_ids.contains([channel.id]),
                Topic.is_demo.is_(False),
                Topic.status.notin_(["archived", "rejected", "edition_rejected"]),
            )
            .order_by(Topic.freshness_score.desc(), Topic.final_score.desc(), Topic.updated_at.desc())
            .limit(40)
        ).scalars()
    )
    for topic in topics:
        score_topic(topic)
    posts = list(
        db.execute(
            select(Post)
            .where(
                Post.channel_id == channel.id,
                Post.is_demo.is_(False),
                Post.mock_only.is_(False),
                Post.provider != "mock",
                Post.generation_mode != "mock",
                Post.status.notin_(["archived", "edition_rejected"]),
            )
            .order_by(Post.created_at.desc())
            .limit(30)
        ).scalars()
    )
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    last_activity = list(
        db.execute(
            select(ActivityEvent)
            .where(
                ((ActivityEvent.entity_type == "channel") & (ActivityEvent.entity_id == channel.id))
                | ((ActivityEvent.entity_type == "platform_channel") & (ActivityEvent.entity_id == (platform.id if platform else -1)))
            )
            .order_by(ActivityEvent.created_at.desc())
            .limit(10)
        ).scalars()
    )
    stats = {
        "sources": len(sources),
        "active_sources": sum(1 for source in sources if source.status == "active"),
        "topics": len(topics),
        "topics_today": sum(1 for topic in topics if topic.created_at and topic.created_at >= today),
        "drafts": sum(1 for post in posts if post.status in {"draft", "needs_review"}),
        "approved": sum(1 for post in posts if post.status in {"approved", "final_pack", "ready_for_manual_copy"}),
        "published": sum(1 for post in posts if post.status == "published" or post.max_message_id),
    }
    db.commit()
    return {
        "channel": ChannelRead.model_validate(channel).model_dump(),
        "platform_channel": _platform_payload(platform),
        "stats": stats,
        "source_coverage": _source_coverage(db, channel, sources),
        "sources": [_source_payload(source) for source in sources],
        "suggested_sources": _suggested_sources(db, channel, attached_source_ids),
        "radar": [_topic_payload(topic) for topic in topics[:20]],
        "topics": [_topic_payload(topic) for topic in topics],
        "posts": [_post_payload(post) for post in posts],
        "last_activity": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "message": event.message,
                "created_at": event.created_at,
                "metadata": event.metadata_json or {},
            }
            for event in last_activity
        ],
    }


@router.post("/{channel_id}/sources/{source_id}/attach", response_model=None)
def attach_source_to_channel(channel_id: int, source_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    channel = db.get(Channel, channel_id)
    source = db.get(Source, source_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    existing = db.execute(
        select(SourceChannelMap).where(SourceChannelMap.channel_id == channel.id, SourceChannelMap.source_id == source.id)
    ).scalar_one_or_none()
    if existing is None:
        db.add(SourceChannelMap(channel_id=channel.id, source_id=source.id, relevance_weight=1.0, enabled=True))
        action = "attached"
    else:
        existing.enabled = True
        action = "enabled"
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="channel_source_attached",
        entity_type="channel",
        entity_id=channel.id,
        message=f"Source {source.name} {action} for channel {channel.name}.",
        metadata={"channel_id": channel.id, "source_id": source.id, "llm_called": False, "max_called": False},
    )
    db.commit()
    return {"ok": True, "action": action, "channel_id": channel.id, "source": _source_payload(source)}


@router.post("/{channel_id}/ingest-url", response_model=None)
def ingest_url_for_channel(channel_id: int, payload: ChannelUrlIngestRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    url = (payload.url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Paste a full http(s) news URL")

    source = db.execute(select(Source).where(Source.url == url, Source.is_demo.is_(False))).scalar_one_or_none()
    created_source = False
    if source is None:
        host = parsed.netloc.replace("www.", "")
        source = Source(
            name=(payload.title or f"Manual URL: {host}")[:180],
            url=url,
            type="manual_url",
            language="",
            trust_score=0.65,
            reliability_score=0.65,
            speed_score=0.5,
            noise_score=0.25,
            status="active",
            ingestion_enabled=True,
            requires_review=True,
            requires_operator_approval=True,
            source_priority="normal",
            source_quality_tier="manual_url",
        )
        db.add(source)
        db.flush()
        created_source = True

    mapping = db.execute(
        select(SourceChannelMap).where(SourceChannelMap.channel_id == channel.id, SourceChannelMap.source_id == source.id)
    ).scalar_one_or_none()
    if mapping is None:
        db.add(SourceChannelMap(channel_id=channel.id, source_id=source.id, relevance_weight=1.0, enabled=True))
    else:
        mapping.enabled = True

    result = SourceFetchService().fetch_source(db, source, limit=1, create_topics=True)
    data = result.as_dict()
    topics = list(db.execute(select(Topic).where(Topic.id.in_(data.get("topic_ids") or [-1]))).scalars()) if data.get("topic_ids") else []
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="channel_manual_url_ingested",
        entity_type="channel",
        entity_id=channel.id,
        message=f"Manual URL ingested for channel {channel.name}: {url}",
        metadata={"channel_id": channel.id, "source_id": source.id, "result": data, "llm_called": False, "max_called": False, "published": False},
    )
    db.commit()
    return {
        "ok": True,
        "channel_id": channel.id,
        "created_source": created_source,
        "source": _source_payload(source),
        "result": data,
        "topics": [_topic_payload(topic) for topic in topics],
        "llm_called": False,
        "max_called": False,
        "published": False,
    }


@router.post("/{channel_id}/refresh-radar", response_model=None)
def refresh_channel_radar(
    channel_id: int,
    max_sources: int = Query(default=80, ge=1, le=500),
    limit_per_source: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    sources = list(
        db.execute(
            select(Source)
            .join(SourceChannelMap, SourceChannelMap.source_id == Source.id)
            .where(
                SourceChannelMap.channel_id == channel.id,
                SourceChannelMap.enabled.is_(True),
                Source.status == "active",
                Source.ingestion_enabled.is_(True),
                Source.is_demo.is_(False),
                Source.url != "",
                ~Source.url.ilike("%example.com%"),
            )
            .order_by(Source.last_poll_at.asc().nullsfirst(), Source.reliability_score.desc(), Source.trust_score.desc(), Source.id)
            .limit(max_sources)
        ).scalars()
    )
    service = SourceFetchService()
    totals = {"fetched": 0, "extracted": 0, "topics": 0, "duplicates": 0, "blocked": 0, "failed": 0}
    results: list[dict[str, Any]] = []
    for source in sources:
        result = service.fetch_source(db, source, limit=limit_per_source if source.type == "rss" else 1, create_topics=True)
        data = result.as_dict()
        results.append(data)
        totals["fetched"] += int(data["fetched_count"])
        totals["extracted"] += int(data["extracted_count"])
        totals["topics"] += int(data["topics_created"])
        totals["duplicates"] += int(data["duplicates"])
        totals["blocked"] += int(data["blocked"])
        totals["failed"] += int(data["failed"])
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="channel_radar_refreshed",
        entity_type="channel",
        entity_id=channel.id,
        message=f"Channel radar refreshed for {channel.name}: {len(sources)} sources, {totals['topics']} topics.",
        metadata={"channel_id": channel.id, "sources_scanned": len(sources), "totals": totals, "llm_called": False, "max_called": False, "publishing_called": False},
    )
    db.commit()
    return {"ok": True, "channel_id": channel.id, "sources_scanned": len(sources), "totals": totals, "sample_results": results[:20], "llm_called": False, "max_called": False, "published": False}


@router.post("", response_model=ChannelRead, status_code=status.HTTP_201_CREATED)
def create_channel(payload: ChannelCreate, db: Session = Depends(get_db)) -> Channel:
    channel = Channel(**payload.model_dump())
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/{channel_id}", response_model=ChannelRead)
def get_channel(channel_id: int, db: Session = Depends(get_db)) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.patch("/{channel_id}", response_model=ChannelRead)
def update_channel(channel_id: int, payload: ChannelUpdate, db: Session = Depends(get_db)) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(channel, key, value)
    if channel.publish_mode == "auto":
        channel.auto_publish_enabled = False
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="channel_updated",
        entity_type="channel",
        entity_id=channel.id,
        message=f"Channel updated: {channel.name}",
    )
    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(channel_id: int, db: Session = Depends(get_db)) -> None:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="channel_deleted",
        entity_type="channel",
        entity_id=channel.id,
        message=f"Channel deleted: {channel.name}",
    )
    db.delete(channel)
    db.commit()
