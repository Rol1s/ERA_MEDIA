from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import Channel, PlatformChannel, Post
from app.services.editorial_quality_loop import validate_post_quality_for_approval
from app.services.max_packaging import prepare_max_package
from app.services.media_producer import prepare_media_for_post
from app.services.org import log_activity
from app.services.settings import auto_live_enabled, get_setting
from app.services.visual_media import local_media_path


AUTO_PUBLISH_STATUSES = {"approved", "final_pack", "ready_for_manual_copy"}


def _parse_enabled_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _today_start_utc(timezone_name: str) -> datetime:
    try:
        tz = ZoneInfo(timezone_name or "Europe/Moscow")
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    local_start = datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz)
    return local_start.astimezone(UTC)


def _configured_channel_ids(db: Session) -> set[int]:
    rows = db.execute(
        select(PlatformChannel.channel_id).where(
            PlatformChannel.platform == "max",
            PlatformChannel.status == "connected",
            PlatformChannel.can_publish.is_(True),
        )
    ).all()
    return {int(row[0]) for row in rows}


def _candidate_query(db: Session, *, enabled_since: datetime | None, limit: int):
    channel_ids = _configured_channel_ids(db)
    if not channel_ids:
        return []
    stmt = (
        select(Post)
        .join(Channel, Channel.id == Post.channel_id)
        .where(
            Post.channel_id.in_(channel_ids),
            Channel.status == "active",
            Channel.auto_publish_enabled.is_(True),
            Post.status.in_(AUTO_PUBLISH_STATUSES),
            Post.max_message_id.is_(None),
            Post.mock_only.is_(False),
            Post.is_demo.is_(False),
            Post.provider != "mock",
            Post.generation_mode != "mock",
        )
        .order_by(Post.created_at.asc())
        .limit(limit)
    )
    if enabled_since is not None:
        stmt = stmt.where(Post.created_at >= enabled_since)
    return list(db.execute(stmt).scalars())


def _safe_for_auto_publish(post: Post) -> tuple[bool, str]:
    evidence = (post.structured_outputs_json or {}).get("evidence_pack") or {}
    if evidence.get("risk_level") != "low":
        return False, "auto_publish_safe_mode_requires_low_risk"
    if evidence.get("high_risk") or evidence.get("hard_news"):
        return False, "auto_publish_safe_mode_blocks_high_risk_or_hard_news"
    return True, "ok"


def publish_ready_posts(db: Session, *, dry_run: bool = False) -> dict[str, Any]:
    if not auto_live_enabled(db):
        return {"status": "skipped", "reason": "AUTO_LIVE disabled", "published": [], "blocked": []}
    if not bool(get_setting(db, "auto_publish_enabled")):
        return {"status": "skipped", "reason": "auto_publish_enabled=false", "published": [], "blocked": []}
    if not bool(get_setting(db, "global_publishing_enabled")):
        return {"status": "skipped", "reason": "global_publishing_enabled=false", "published": [], "blocked": []}

    daily_limit = int(get_setting(db, "auto_publish_daily_limit") or 5)
    if daily_limit <= 0:
        return {"status": "skipped", "reason": "auto_publish_daily_limit<=0", "published": [], "blocked": []}

    timezone_name = str(get_setting(db, "auto_publish_timezone") or "Europe/Moscow")
    day_start = _today_start_utc(timezone_name)
    published_today = int(
        db.scalar(
            select(func.count())
            .select_from(Post)
            .where(Post.status == "published", Post.published_at >= day_start, Post.max_message_id.is_not(None))
        )
        or 0
    )
    remaining = max(0, daily_limit - published_today)
    if remaining <= 0:
        return {
            "status": "skipped",
            "reason": "daily_limit_reached",
            "daily_limit": daily_limit,
            "published_today": published_today,
            "published": [],
            "blocked": [],
        }

    enabled_since = _parse_enabled_at(str(get_setting(db, "auto_publish_enabled_at") or ""))
    candidates = _candidate_query(db, enabled_since=enabled_since, limit=remaining)
    published: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for post in candidates:
        try:
            safe, safe_reason = _safe_for_auto_publish(post)
            if not safe:
                raise ValueError(safe_reason)
            if not post.source_urls:
                raise ValueError("source_urls_missing")
            validate_post_quality_for_approval(post)
            if local_media_path(post.image_url) is None:
                try:
                    prepare_media_for_post(db, post, generate_fallback=True)
                    db.flush()
                except Exception as exc:
                    log_activity(
                        db,
                        actor_type="system",
                        actor_id=None,
                        event_type="auto_publish_media_warning",
                        entity_type="post",
                        entity_id=post.id,
                        message=f"Auto publish media step warning for post #{post.id}: {exc}",
                        metadata={"error": str(exc)[:500]},
                    )
            if not post.max_packaged_text:
                prepare_max_package(db, post)
                db.flush()
            if dry_run:
                published.append({"post_id": post.id, "title": post.title, "dry_run": True})
                continue

            from app.api.routes.posts import MaxPublishRequest, publish_to_max

            publish_to_max(
                post.id,
                MaxPublishRequest(confirm=True, note="Auto-published by guarded ERA autopublisher."),
                db,
            )
            published.append({"post_id": post.id, "title": post.title})
        except HTTPException as exc:
            blocked.append({"post_id": post.id, "title": post.title, "reason": str(exc.detail)})
            log_activity(
                db,
                actor_type="system",
                actor_id=None,
                event_type="auto_publish_blocked",
                entity_type="post",
                entity_id=post.id,
                message=f"Auto publish blocked for post #{post.id}: {exc.detail}",
                metadata={"status_code": exc.status_code, "reason": str(exc.detail)[:500]},
            )
            db.commit()
        except Exception as exc:
            blocked.append({"post_id": post.id, "title": post.title, "reason": str(exc)})
            log_activity(
                db,
                actor_type="system",
                actor_id=None,
                event_type="auto_publish_blocked",
                entity_type="post",
                entity_id=post.id,
                message=f"Auto publish blocked for post #{post.id}: {exc}",
                metadata={"reason": str(exc)[:500]},
            )
            db.commit()

    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="auto_publish_cycle_completed",
        entity_type="post",
        entity_id=None,
        message=f"Auto publish cycle completed: {len(published)} published, {len(blocked)} blocked.",
        metadata={
            "dry_run": dry_run,
            "daily_limit": daily_limit,
            "published_today_before": published_today,
            "remaining_before": remaining,
            "published": published,
            "blocked": blocked,
        },
    )
    db.commit()
    return {
        "status": "ok",
        "daily_limit": daily_limit,
        "published_today_before": published_today,
        "remaining_before": remaining,
        "published": published,
        "blocked": blocked,
    }
