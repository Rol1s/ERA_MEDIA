from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.agents.orchestrator import PipelineError, run_real_dry_run_pipeline
from app.models.all_models import Channel, PlatformChannel, Post, Topic
from app.services.auto_publisher import publish_ready_posts
from app.services.editorial_quality_loop import validate_post_quality_for_approval
from app.services.max_packaging import prepare_max_package
from app.services.media_producer import prepare_media_for_post
from app.services.org import log_activity
from app.services.settings import get_setting


READY_TOPIC_STATUSES = {"ready_for_dry_run", "selected", "researched", "edition_selected"}
AUTO_ALLOWED_RISK_CATEGORIES = {"food"}


def _topic_text(topic: Topic) -> str:
    return " ".join([topic.title or "", topic.summary or "", topic.raw_text or "", topic.why_this_matters or ""]).lower()


def _topic_is_low_risk_candidate(topic: Topic, channel_categories: dict[int, str]) -> bool:
    if float(topic.risk_score or 0) >= 0.1:
        return False
    categories = {channel_categories.get(int(channel_id), "") for channel_id in (topic.assigned_channel_ids or [])}
    categories.discard("")
    if categories and categories <= AUTO_ALLOWED_RISK_CATEGORIES:
        text = _topic_text(topic)
        return not any(marker in text for marker in {"recall", "outbreak", "illness", "disease", "salmonella", "listeria", "e. coli", "аллерг", "отрав", "болезн", "вспышк"})
    text = _topic_text(topic)
    risky_markers = {"war", "войн", "attack", "удар", "health", "здоров", "court", "суд", "crime", "кримин", "finance", "финанс", "politic", "полит", "death", "смерт"}
    return not any(marker in text for marker in risky_markers)


def _today_start_utc(timezone_name: str) -> datetime:
    try:
        tz = ZoneInfo(timezone_name or "Europe/Moscow")
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    return datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz).astimezone(UTC)


def _connected_auto_channel_ids(db: Session) -> set[int]:
    rows = db.execute(
        select(PlatformChannel.channel_id)
        .join(Channel, Channel.id == PlatformChannel.channel_id)
        .where(
            PlatformChannel.platform == "max",
            PlatformChannel.status == "connected",
            PlatformChannel.can_publish.is_(True),
            Channel.status == "active",
            Channel.auto_publish_enabled.is_(True),
        )
    ).all()
    return {int(row[0]) for row in rows}


def _published_today(db: Session) -> int:
    timezone_name = str(get_setting(db, "auto_publish_timezone") or "Europe/Moscow")
    day_start = _today_start_utc(timezone_name)
    return int(
        db.scalar(
            select(func.count())
            .select_from(Post)
            .where(Post.status == "published", Post.published_at >= day_start, Post.max_message_id.is_not(None))
        )
        or 0
    )


def _topic_channel_id(topic: Topic, allowed_channel_ids: set[int]) -> int | None:
    for channel_id in topic.assigned_channel_ids or []:
        if int(channel_id) in allowed_channel_ids:
            return int(channel_id)
    return None


def _candidate_topics(db: Session, *, limit: int, allowed_channel_ids: set[int]) -> list[Topic]:
    if not allowed_channel_ids:
        return []
    since = datetime.now(UTC) - timedelta(hours=36)
    stmt = (
        select(Topic)
        .where(
            Topic.is_demo.is_(False),
            Topic.status.in_(READY_TOPIC_STATUSES),
            Topic.url != "",
            Topic.created_at >= since,
            or_(*[Topic.assigned_channel_ids.contains([channel_id]) for channel_id in allowed_channel_ids]),
        )
        .order_by(
            Topic.freshness_score.desc(),
            Topic.importance_score.desc(),
            Topic.final_score.desc(),
            Topic.updated_at.desc(),
        )
        .limit(max(limit * 4, limit))
    )
    topics = list(db.execute(stmt).scalars())
    selected: list[Topic] = []
    seen_clusters: set[str] = set()
    for topic in topics:
        cluster = topic.story_cluster_id or f"topic:{topic.id}"
        if cluster in seen_clusters:
            continue
        seen_clusters.add(cluster)
        selected.append(topic)
        if len(selected) >= limit:
            break
    return selected


def _candidate_topics_for_channel(db: Session, *, channel_id: int, limit: int) -> list[Topic]:
    since = datetime.now(UTC) - timedelta(hours=72)
    stmt = (
        select(Topic)
        .where(
            Topic.is_demo.is_(False),
            Topic.status.in_(READY_TOPIC_STATUSES),
            Topic.url != "",
            Topic.created_at >= since,
            Topic.assigned_channel_ids.contains([channel_id]),
            Topic.risk_score < 0.1,
        )
        .order_by(
            Topic.risk_score.asc(),
            Topic.final_score.desc(),
            Topic.freshness_score.desc(),
            Topic.updated_at.desc(),
        )
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def _balanced_candidate_topics(db: Session, *, limit: int, allowed_channel_ids: set[int]) -> list[Topic]:
    selected: list[Topic] = []
    seen_ids: set[int] = set()
    channel_categories = {
        int(channel.id): channel.category
        for channel in db.execute(select(Channel).where(Channel.id.in_(allowed_channel_ids))).scalars()
    }
    for channel_id in sorted(allowed_channel_ids):
        for topic in _candidate_topics_for_channel(db, channel_id=channel_id, limit=3):
            if topic.id in seen_ids:
                continue
            if not _topic_is_low_risk_candidate(topic, channel_categories):
                continue
            selected.append(topic)
            seen_ids.add(topic.id)
            break
        if len(selected) >= limit:
            return selected

    for topic in _candidate_topics(db, limit=max(limit * 4, limit), allowed_channel_ids=allowed_channel_ids):
        if topic.id in seen_ids:
            continue
        if not _topic_is_low_risk_candidate(topic, channel_categories):
            continue
        selected.append(topic)
        seen_ids.add(topic.id)
        if len(selected) >= limit:
            break
    return selected


def _auto_approve_if_safe(db: Session, post: Post, *, max_risk: float, min_quality: float) -> tuple[bool, str]:
    if post.status == "published":
        return False, "already_published"
    if post.mock_only or post.is_demo or post.provider == "mock" or post.generation_mode == "mock":
        return False, "mock_or_demo_blocked"
    if not post.source_urls:
        return False, "source_urls_missing"
    if float(post.risk_score or 0) > max_risk:
        return False, f"risk_score_too_high:{post.risk_score}"
    if float(post.quality_score or 0) < min_quality:
        return False, f"quality_score_too_low:{post.quality_score}"
    try:
        validate_post_quality_for_approval(post)
    except ValueError as exc:
        return False, str(exc)
    evidence = (post.structured_outputs_json or {}).get("evidence_pack") or {}
    if evidence.get("risk_level") != "low" or evidence.get("high_risk") or evidence.get("hard_news"):
        return False, "autopublish_safe_mode_requires_low_risk"

    post.status = "approved"
    post.approved_by = "senior_editor_autopilot"
    post.publishable = False
    post.non_publishable_reason = "Approved by senior editor autopilot. Guarded MAX autopublisher may publish it."
    log_activity(
        db,
        actor_type="agent",
        actor_id=None,
        event_type="senior_editor_auto_approved",
        entity_type="post",
        entity_id=post.id,
        message=f"Senior editor autopilot approved post #{post.id} for guarded MAX publishing.",
        metadata={"risk_score": post.risk_score, "quality_score": post.quality_score},
    )
    db.flush()
    return True, "approved"


def run_editorial_autopilot(db: Session, *, max_posts: int | None = None) -> dict[str, Any]:
    if not bool(get_setting(db, "editorial_autopilot_enabled")):
        return {"status": "skipped", "reason": "editorial_autopilot_enabled=false", "generated": [], "approved": [], "published": []}
    if not bool(get_setting(db, "auto_publish_enabled")):
        return {"status": "skipped", "reason": "auto_publish_enabled=false", "generated": [], "approved": [], "published": []}
    if not bool(get_setting(db, "global_publishing_enabled")):
        return {"status": "skipped", "reason": "global_publishing_enabled=false", "generated": [], "approved": [], "published": []}

    daily_limit = int(get_setting(db, "auto_publish_daily_limit") or 5)
    remaining = max(0, daily_limit - _published_today(db))
    if remaining <= 0:
        return {"status": "skipped", "reason": "daily_limit_reached", "daily_limit": daily_limit, "generated": [], "approved": [], "published": []}

    batch_size = int(max_posts or get_setting(db, "editorial_autopilot_batch_size") or 2)
    batch_size = max(1, min(batch_size, remaining, 5))
    max_risk = float(get_setting(db, "editorial_autopilot_max_risk_score") or 45)
    min_quality = float(get_setting(db, "editorial_autopilot_min_quality_score") or 82)
    allowed_channel_ids = _connected_auto_channel_ids(db)

    generated: list[dict[str, Any]] = []
    approved: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    topics = _balanced_candidate_topics(db, limit=batch_size, allowed_channel_ids=allowed_channel_ids)

    for topic in topics:
        channel_id = _topic_channel_id(topic, allowed_channel_ids)
        if channel_id is None:
            blocked.append({"topic_id": topic.id, "reason": "no_connected_auto_channel"})
            continue
        try:
            post = run_real_dry_run_pipeline(db, topic_id=topic.id, channel_id=channel_id)
            generated.append({"topic_id": topic.id, "post_id": post.id, "title": post.title, "status": post.status})
            try:
                prepare_media_for_post(db, post, generate_fallback=True)
            except Exception as exc:
                log_activity(
                    db,
                    actor_type="agent",
                    actor_id=None,
                    event_type="autopilot_media_warning",
                    entity_type="post",
                    entity_id=post.id,
                    message=f"Autopilot media step warning for post #{post.id}: {exc}",
                    metadata={"error": str(exc)[:500]},
                )
            prepare_max_package(db, post)
            ok, reason = _auto_approve_if_safe(db, post, max_risk=max_risk, min_quality=min_quality)
            if ok:
                approved.append({"post_id": post.id, "title": post.title})
            else:
                post.status = "needs_review"
                post.status_reason = f"Autopilot did not approve: {reason}"
                blocked.append({"post_id": post.id, "topic_id": topic.id, "reason": reason})
            db.commit()
        except PipelineError as exc:
            blocked.append({"topic_id": topic.id, "reason": str(exc)})
            db.commit()
        except Exception as exc:
            blocked.append({"topic_id": topic.id, "reason": str(exc)})
            db.commit()

    publish_result = publish_ready_posts(db, dry_run=False)
    log_activity(
        db,
        actor_type="agent",
        actor_id=None,
        event_type="editorial_autopilot_cycle_completed",
        entity_type="post",
        entity_id=None,
        message=f"Editorial autopilot: generated {len(generated)}, approved {len(approved)}, published {len(publish_result.get('published', []))}.",
        metadata={"generated": generated, "approved": approved, "blocked": blocked, "publish_result": publish_result},
    )
    db.commit()
    return {
        "status": "ok",
        "daily_limit": daily_limit,
        "remaining_before": remaining,
        "topics_seen": [topic.id for topic in topics],
        "generated": generated,
        "approved": approved,
        "blocked": blocked,
        "publish_result": publish_result,
    }
