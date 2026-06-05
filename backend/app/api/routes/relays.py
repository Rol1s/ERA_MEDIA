from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import ActivityEvent, Channel, Integration, PlatformChannel, Post, Source, SourceChannelMap
from app.services.ft_live_monitor import run_ft_live_monitor
from app.services.org import log_activity

router = APIRouter()


class RelayCreate(BaseModel):
    name: str
    slug: str = ""
    max_chat_id: str = ""
    max_url: str = ""
    source_urls: list[str] = Field(default_factory=list)
    max_posts_per_day: int = 5
    check_interval_minutes: int = 5
    auto_publish_low_risk: bool = False


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "relay"


def _source_name(url: str) -> str:
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])
    return host or url[:80]


def _relay_payload(db: Session, channel: Channel) -> dict[str, Any]:
    source_ids = [int(item) for item in (channel.relay_source_ids or []) if str(item).isdigit()]
    sources = list(db.execute(select(Source).where(Source.id.in_(source_ids)).order_by(Source.id)).scalars()) if source_ids else []
    recent_posts = list(db.execute(select(Post).where(Post.channel_id == channel.id).order_by(Post.id.desc()).limit(8)).scalars())
    platform = db.execute(select(PlatformChannel).where(PlatformChannel.channel_id == channel.id, PlatformChannel.platform == "max")).scalar_one_or_none()
    last_run = db.execute(
        select(ActivityEvent)
        .where(ActivityEvent.entity_type == "channel", ActivityEvent.entity_id == channel.id, ActivityEvent.event_type == "ft_live_monitor_completed")
        .order_by(ActivityEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return {
        "id": channel.id,
        "name": channel.name,
        "slug": channel.slug,
        "status": channel.status,
        "auto_publish_enabled": channel.auto_publish_enabled,
        "relay_mode": channel.relay_mode,
        "relay_source_ids": source_ids,
        "relay_max_posts_per_day": channel.relay_max_posts_per_day,
        "relay_publish_delay_minutes": channel.relay_publish_delay_minutes,
        "sources": [{"id": source.id, "name": source.name, "url": source.url, "status": source.status} for source in sources],
        "max": {
            "chat_id": platform.external_chat_id if platform else "",
            "url": platform.external_channel_url if platform else "",
            "status": platform.status if platform else "not_connected",
            "can_publish": bool(platform.can_publish) if platform else False,
        },
        "has_posts": bool(recent_posts),
        "last_run": {
            "created_at": last_run.created_at.isoformat() if last_run else None,
            "message": last_run.message if last_run else "",
            "metadata": last_run.metadata_json or {} if last_run else {},
        },
        "recent_posts": [
            {
                "id": post.id,
                "status": post.status,
                "title": post.title,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "source_urls": post.source_urls or [],
            }
            for post in recent_posts
        ],
    }


@router.get("", response_model=None)
def list_relays(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    channels = list(db.execute(select(Channel).where(Channel.channel_mode == "relay").order_by(Channel.id.desc())).scalars())
    return [_relay_payload(db, channel) for channel in channels]


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
def create_relay(payload: RelayCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    source_urls = [url.strip() for url in payload.source_urls if url.strip()]
    if not source_urls:
        raise HTTPException(status_code=422, detail="Нужен хотя бы один RSS/URL источник")
    slug = payload.slug.strip() or _slug(payload.name)
    existing = db.execute(select(Channel).where((Channel.slug == slug) | (Channel.name == payload.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=422, detail="Канал с таким названием или slug уже есть")

    channel = Channel(
        name=payload.name.strip(),
        slug=slug,
        category="relay",
        description="Live-ретранслятор одного или нескольких источников на русском языке.",
        tone_of_voice="Коротко, ясно, по-русски, без выдуманных фактов.",
        audience_description="Читатели MAX, которым нужна быстрая русская версия выбранного источника.",
        posting_frequency_per_day=max(1, min(payload.max_posts_per_day, 30)),
        daily_post_limit=max(1, min(payload.max_posts_per_day, 30)),
        publish_mode="auto" if payload.auto_publish_low_risk else "manual",
        auto_publish_enabled=payload.auto_publish_low_risk,
        channel_mode="relay",
        relay_mode="single_source_live" if len(source_urls) == 1 else "multi_source_live",
        relay_publish_delay_minutes=0,
        relay_max_posts_per_day=max(1, min(payload.max_posts_per_day, 30)),
        status="active",
    )
    db.add(channel)
    db.flush()

    source_ids: list[int] = []
    for url in source_urls:
        source = db.execute(select(Source).where(Source.url == url)).scalar_one_or_none()
        if source is None:
            source = Source(
                name=_source_name(url),
                url=url,
                type="rss" if "rss" in url.lower() or "feed" in url.lower() else "site",
                language="en",
                trust_score=0.85,
                source_quality_tier="reputable_media",
                source_priority="high",
                poll_interval_minutes=max(5, min(payload.check_interval_minutes, 180)),
                check_interval_minutes=max(5, min(payload.check_interval_minutes, 180)),
                ingestion_enabled=True,
                requires_operator_approval=False,
                status="active",
            )
            db.add(source)
            db.flush()
        source_ids.append(source.id)
        if not db.execute(select(SourceChannelMap).where(SourceChannelMap.source_id == source.id, SourceChannelMap.channel_id == channel.id)).scalar_one_or_none():
            db.add(SourceChannelMap(source_id=source.id, channel_id=channel.id, relevance_weight=1.0, enabled=True))

    channel.relay_source_ids = source_ids
    integration = db.execute(select(Integration).where(Integration.provider == "max")).scalar_one_or_none()
    db.add(
        PlatformChannel(
            channel_id=channel.id,
            platform="max",
            external_chat_id=payload.max_chat_id.strip(),
            external_channel_url=payload.max_url.strip(),
            integration_id=integration.id if integration else None,
            status="connected" if payload.max_chat_id.strip() else "not_connected",
            publish_mode="api" if payload.max_chat_id.strip() else "manual_copy",
            can_publish=bool(payload.max_chat_id.strip()),
        )
    )
    log_activity(db, actor_type="human", actor_id=None, event_type="relay_created", entity_type="channel", entity_id=channel.id, message=f"Relay channel created: {channel.name}")
    db.commit()
    db.refresh(channel)
    return _relay_payload(db, channel)


@router.post("/{channel_id}/run", response_model=None)
def run_relay(channel_id: int, max_posts: int | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    channel = db.get(Channel, channel_id)
    if channel is None or channel.channel_mode != "relay":
        raise HTTPException(status_code=404, detail="Relay channel not found")
    return run_ft_live_monitor(db, max_posts=max_posts or channel.relay_max_posts_per_day or 3, channel_id=channel.id)
