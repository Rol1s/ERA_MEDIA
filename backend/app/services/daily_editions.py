from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.orchestrator import PipelineError, request_post_rewrite, run_real_dry_run_pipeline
from app.models.all_models import Channel, DailyEdition, Post, Source, SourceChannelMap, Topic
from app.services.org import log_activity
from app.services.source_ingestion import SourceFetchService

EDITION_CHANNELS = ["era-ai", "era-money"]
TARGET_TOPICS = 10
TARGET_POSTS = 5

CURATED_SOURCES = {
    "era-ai": [
        ("ERA AI / Google AI Blog", "https://blog.google/technology/ai/rss/", "rss"),
        ("ERA AI / OpenAI Models", "https://platform.openai.com/docs/models", "website"),
        ("ERA AI / OpenAI Agents", "https://platform.openai.com/docs/guides/agents", "website"),
    ],
    "era-money": [
        ("ERA Money / NIST News", "https://www.nist.gov/news-events/news/rss.xml", "rss"),
        ("ERA Money / SBA Finances", "https://www.sba.gov/business-guide/manage-your-business/manage-your-finances", "website"),
        ("ERA Money / SBA Cash Flow", "https://www.sba.gov/business-guide/manage-your-business/prepare-emergencies", "website"),
    ],
}


def today_utc() -> date:
    return datetime.now(UTC).date()


def ensure_daily_edition(db: Session, channel: Channel, *, edition_date: date | None = None) -> DailyEdition:
    edition_date = edition_date or today_utc()
    edition = db.execute(
        select(DailyEdition).where(DailyEdition.date == edition_date, DailyEdition.channel_id == channel.id)
    ).scalar_one_or_none()
    if edition is None:
        edition = DailyEdition(
            date=edition_date,
            channel_id=channel.id,
            status="collecting",
            target_topics_count=TARGET_TOPICS,
            target_posts_count=TARGET_POSTS,
        )
        db.add(edition)
        db.flush()
        log_activity(
            db,
            actor_type="human",
            actor_id=None,
            event_type="daily_edition_created",
            entity_type="daily_edition",
            entity_id=edition.id,
            message=f"Daily edition created for {channel.name}.",
        )
        db.commit()
        db.refresh(edition)
    refresh_edition_counts(db, edition)
    return edition


def ensure_today_editions(db: Session) -> list[DailyEdition]:
    channels = db.execute(select(Channel).where(Channel.slug.in_(EDITION_CHANNELS)).order_by(Channel.slug)).scalars().all()
    return [ensure_daily_edition(db, channel) for channel in channels]


def ensure_curated_sources(db: Session, channel: Channel) -> list[Source]:
    sources: list[Source] = []
    for name, url, type_ in CURATED_SOURCES.get(channel.slug, []):
        source = db.execute(select(Source).where(Source.name == name)).scalar_one_or_none()
        if source is None:
            source = Source(name=name, url=url, type=type_, language="en", trust_score=0.85, status="active", requires_review=True)
            db.add(source)
            db.flush()
        source.url = url
        source.type = type_
        source.language = "en"
        source.trust_score = max(float(source.trust_score or 0), 0.8)
        source.status = "active"
        mapping = db.execute(
            select(SourceChannelMap).where(SourceChannelMap.source_id == source.id, SourceChannelMap.channel_id == channel.id)
        ).scalar_one_or_none()
        if mapping is None:
            db.add(SourceChannelMap(source_id=source.id, channel_id=channel.id, relevance_weight=1.0, enabled=True))
        sources.append(source)
    db.commit()
    return sources


def collect_candidates(db: Session, edition: DailyEdition, *, limit_per_source: int = 5) -> dict[str, Any]:
    channel = edition.channel
    sources = ensure_curated_sources(db, channel)
    service = SourceFetchService()
    source_results = []
    for source in sources:
        result = service.fetch_source(db, source, limit=limit_per_source if source.type == "rss" else 1, create_topics=True)
        source_results.append(result.as_dict())
        for topic_id in result.topic_ids:
            topic = db.get(Topic, topic_id)
            if topic and topic.status == "ready_for_dry_run":
                topic.daily_edition_id = edition.id
                if channel.id not in (topic.assigned_channel_ids or []):
                    topic.assigned_channel_ids = [channel.id, *(topic.assigned_channel_ids or [])]

    candidates = candidate_topics(db, edition, include_unassigned=True)
    for topic in candidates[: edition.target_topics_count]:
        topic.daily_edition_id = edition.id
    edition.status = "collecting"
    refresh_edition_counts(db, edition)
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="daily_edition_candidates_collected",
        entity_type="daily_edition",
        entity_id=edition.id,
        message=f"Collected candidates for {channel.name}.",
        metadata={"sources": source_results, "candidate_count": len(candidates)},
    )
    db.commit()
    db.refresh(edition)
    return {"edition": edition_payload(db, edition), "sources": source_results}


def candidate_topics(db: Session, edition: DailyEdition, *, include_unassigned: bool = False) -> list[Topic]:
    stmt = select(Topic).where(
        Topic.status.in_(["ready_for_dry_run", "edition_selected", "edition_rejected"]),
        Topic.assigned_channel_ids.contains([edition.channel_id]),
    )
    if include_unassigned:
        stmt = stmt.where((Topic.daily_edition_id == edition.id) | (Topic.daily_edition_id.is_(None)))
    else:
        stmt = stmt.where(Topic.daily_edition_id == edition.id)
    return list(db.execute(stmt.order_by(Topic.final_score.desc(), Topic.created_at.desc()).limit(50)).scalars())


def select_top_topics(db: Session, edition: DailyEdition, *, count: int | None = None) -> list[Topic]:
    count = count or edition.target_posts_count
    existing = [topic for topic in candidate_topics(db, edition) if topic.status in {"edition_selected", "edition_generated"}]
    if len(existing) >= count:
        return existing[:count]
    topics = [topic for topic in candidate_topics(db, edition) if topic.status == "ready_for_dry_run"]
    selected = topics[:count]
    for topic in selected:
        topic.status = "edition_selected"
        topic.daily_edition_id = edition.id
    edition.status = "drafting"
    refresh_edition_counts(db, edition)
    log_activity(db, actor_type="human", actor_id=None, event_type="daily_edition_topics_selected", entity_type="daily_edition", entity_id=edition.id, message=f"Selected {len(selected)} topics for edition.")
    db.commit()
    return selected


def select_topic(db: Session, edition: DailyEdition, topic_id: int) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise PipelineError("Topic not found")
    topic.daily_edition_id = edition.id
    topic.status = "edition_selected"
    refresh_edition_counts(db, edition)
    log_activity(db, actor_type="human", actor_id=None, event_type="edition_topic_selected", entity_type="topic", entity_id=topic.id, message=f"Topic selected for edition #{edition.id}.")
    db.commit()
    db.refresh(topic)
    return topic


def reject_topic(db: Session, edition: DailyEdition, topic_id: int) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise PipelineError("Topic not found")
    topic.daily_edition_id = edition.id
    topic.status = "edition_rejected"
    refresh_edition_counts(db, edition)
    log_activity(db, actor_type="human", actor_id=None, event_type="edition_topic_rejected", entity_type="topic", entity_id=topic.id, message=f"Topic rejected for edition #{edition.id}.")
    db.commit()
    db.refresh(topic)
    return topic


def generate_post_for_topic(db: Session, edition: DailyEdition, topic_id: int) -> Post:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise PipelineError("Topic not found")
    if topic.status == "edition_generated":
        existing = db.execute(
            select(Post)
            .where(Post.daily_edition_id == edition.id, Post.topic_id == topic.id)
            .order_by(Post.created_at.desc(), Post.id.desc())
        ).scalars().first()
        if existing is not None:
            return existing
    if topic.status not in {"edition_selected", "ready_for_dry_run"}:
        raise PipelineError("Select topic before generating a post")
    post = run_real_dry_run_pipeline(db, topic_id=topic.id, channel_id=edition.channel_id)
    post.daily_edition_id = edition.id
    topic.daily_edition_id = edition.id
    topic.status = "edition_generated"
    edition.status = "review"
    refresh_edition_counts(db, edition)
    log_activity(db, actor_type="system", actor_id=None, event_type="edition_post_generated", entity_type="post", entity_id=post.id, message=f"Dry-run post generated for edition #{edition.id}.")
    db.commit()
    db.refresh(post)
    return post


def regenerate_post_once(db: Session, edition: DailyEdition, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise PipelineError("Post not found")
    if post.daily_edition_id != edition.id:
        raise PipelineError("Post does not belong to this edition")
    regenerated = request_post_rewrite(db, post.id, notes=["edition_regenerate_once"])
    regenerated.daily_edition_id = edition.id
    refresh_edition_counts(db, edition)
    db.commit()
    db.refresh(regenerated)
    return regenerated


def approve_post_for_final_pack(db: Session, edition: DailyEdition, post_id: int, *, human_note: str = "") -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise PipelineError("Post not found")
    if post.daily_edition_id != edition.id:
        raise PipelineError("Post does not belong to this edition")
    reason = final_pack_block_reason(post, edition, human_note=human_note)
    if reason:
        raise PipelineError(reason)
    post.status = "final_pack"
    post.approved_by = "human_editor"
    post.status_reason = "Approved for internal final pack. Manual MAX publishing only."
    data = dict(post.structured_outputs_json or {})
    data["final_pack"] = {"approved": True, "human_note": human_note, "approved_at": datetime.now(UTC).isoformat()}
    post.structured_outputs_json = data
    refresh_edition_counts(db, edition)
    if edition.approved_posts_count >= edition.target_posts_count:
        edition.status = "ready"
    log_activity(db, actor_type="human", actor_id=None, event_type="edition_post_approved_final_pack", entity_type="post", entity_id=post.id, message=f"Post approved for final pack in edition #{edition.id}.")
    db.commit()
    db.refresh(post)
    return post


def reject_post_for_edition(db: Session, edition: DailyEdition, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise PipelineError("Post not found")
    if post.daily_edition_id != edition.id:
        raise PipelineError("Post does not belong to this edition")
    post.status = "edition_rejected"
    post.status_reason = "Rejected from daily edition."
    refresh_edition_counts(db, edition)
    log_activity(db, actor_type="human", actor_id=None, event_type="edition_post_rejected", entity_type="post", entity_id=post.id, message=f"Post rejected from edition #{edition.id}.")
    db.commit()
    db.refresh(post)
    return post


def final_pack_block_reason(post: Post, edition: DailyEdition, *, human_note: str = "") -> str:
    if post.generation_mode != "dry_run":
        return "Final pack accepts only dry-run posts."
    if post.quality_score < 75:
        return "Quality score must be at least 75."
    factcheck = (post.structured_outputs_json or {}).get("factcheck") or {}
    if (factcheck.get("factcheck_result") or factcheck.get("result")) == "fail":
        return "Factcheck failed."
    if post.risk_score > (edition.channel.risk_threshold * 100 if edition.channel.risk_threshold <= 1 else edition.channel.risk_threshold) and not human_note.strip():
        return "High risk requires a human note before final pack."
    if not post.source_urls:
        return "Post must include source URL."
    return ""


def refresh_edition_counts(db: Session, edition: DailyEdition) -> DailyEdition:
    edition.selected_topics_count = int(db.scalar(select(func.count()).select_from(Topic).where(Topic.daily_edition_id == edition.id, Topic.status.in_(["edition_selected", "edition_generated"]))) or 0)
    edition.generated_posts_count = int(db.scalar(select(func.count()).select_from(Post).where(Post.daily_edition_id == edition.id)) or 0)
    edition.approved_posts_count = int(db.scalar(select(func.count()).select_from(Post).where(Post.daily_edition_id == edition.id, Post.status == "final_pack")) or 0)
    edition.rejected_posts_count = int(db.scalar(select(func.count()).select_from(Post).where(Post.daily_edition_id == edition.id, Post.status.in_(["rejected", "edition_rejected"]))) or 0)
    return edition


def edition_cost(db: Session, edition: DailyEdition) -> float:
    post_cost = sum(float(post.estimated_cost_usd or 0) for post in db.execute(select(Post).where(Post.daily_edition_id == edition.id)).scalars())
    return round(post_cost, 6)


def next_action(db: Session, edition: DailyEdition) -> str:
    topics = candidate_topics(db, edition)
    if len(topics) < edition.target_topics_count:
        return "Собрать материалы из curated источников"
    if edition.selected_topics_count < edition.target_posts_count:
        return "Выбрать темы для выпуска"
    if edition.generated_posts_count < edition.target_posts_count:
        return "Сгенерировать dry-run посты"
    if edition.approved_posts_count < edition.target_posts_count:
        return "Проверить посты и собрать final pack"
    return "Выпуск готов для ручной подготовки в MAX"


def edition_payload(db: Session, edition: DailyEdition) -> dict[str, Any]:
    refresh_edition_counts(db, edition)
    return {
        "id": edition.id,
        "date": edition.date.isoformat(),
        "channel_id": edition.channel_id,
        "channel_name": edition.channel.name if edition.channel else "",
        "channel_slug": edition.channel.slug if edition.channel else "",
        "status": edition.status,
        "target_topics_count": edition.target_topics_count,
        "target_posts_count": edition.target_posts_count,
        "selected_topics_count": edition.selected_topics_count,
        "generated_posts_count": edition.generated_posts_count,
        "approved_posts_count": edition.approved_posts_count,
        "rejected_posts_count": edition.rejected_posts_count,
        "editor_notes": edition.editor_notes,
        "cost": edition_cost(db, edition),
        "next_action": next_action(db, edition),
        "created_at": edition.created_at,
        "updated_at": edition.updated_at,
    }


def edition_detail_payload(db: Session, edition: DailyEdition) -> dict[str, Any]:
    sources = ensure_curated_sources(db, edition.channel)
    topics = list(db.execute(select(Topic).where(Topic.daily_edition_id == edition.id).order_by(Topic.final_score.desc(), Topic.id.desc())).scalars())
    posts = list(db.execute(select(Post).where(Post.daily_edition_id == edition.id).order_by(Post.created_at.desc())).scalars())
    return {
        "edition": edition_payload(db, edition),
        "sources": sources,
        "candidate_topics": [topic for topic in topics if topic.status in {"ready_for_dry_run", "edition_selected", "edition_generated"}],
        "selected_topics": [topic for topic in topics if topic.status in {"edition_selected", "edition_generated"}],
        "rejected_topics": [topic for topic in topics if topic.status in {"edition_rejected", "duplicate", "rejected", "blocked_source"}],
        "generated_posts": posts,
        "final_pack_posts": [post for post in posts if post.status == "final_pack"],
        "rejected_posts": [post for post in posts if post.status in {"rejected", "edition_rejected"}],
    }
