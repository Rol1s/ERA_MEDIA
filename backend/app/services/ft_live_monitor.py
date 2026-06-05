from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import Channel, Post, Source, SourceChannelMap, Topic
from app.services.cost_optimizer import get_cached_llm_json, put_cached_llm_json
from app.services.llm_config import provider_for_agent
from app.services.max_packaging import prepare_max_package
from app.services.media_producer import prepare_media_for_post
from app.services.org import log_activity
from app.services.public_sources import public_source_urls
from app.services.settings import get_setting
from app.services.source_ingestion import SourceFetchService
from app.services.zero_token_guard import zero_token_metadata


FT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "body", "why_it_matters", "uncertainty_note"],
    "properties": {
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "uncertainty_note": {"type": "string"},
    },
}

HIGH_RISK_MARKERS = {
    "war",
    "attack",
    "killed",
    "death",
    "court",
    "lawsuit",
    "fraud",
    "health",
    "children",
    "iran",
    "ukraine",
    "russia",
    "israel",
    "gaza",
    "войн",
    "удар",
    "погиб",
    "суд",
    "здоров",
    "дет",
    "финанс",
    "полит",
}


def _clean_url(url: str) -> str:
    return (url or "").split("?")[0].strip()


def _source_text(topic: Topic) -> str:
    return " ".join([topic.title or "", topic.summary or "", topic.raw_text or ""]).strip()


def _extract_numbers(text: str) -> set[str]:
    import re

    clean = text.replace("\u00a0", " ").replace(",", "")
    return {match.group(0) for match in re.finditer(r"\b\d{1,4}(?:[./-]\d{1,4})?(?:[./-]\d{1,4})?%?\b", clean)}


def _is_high_risk(topic: Topic) -> bool:
    if float(topic.risk_score or 0) >= 0.35:
        return True
    text = _source_text(topic).lower()
    return any(marker in text for marker in HIGH_RISK_MARKERS)


def _is_poor_rss(topic: Topic) -> bool:
    return len((topic.summary or topic.raw_text or "").strip()) < 80


def _relay_code_guard(topic: Topic, data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    source_text = _source_text(topic)
    draft_text = " ".join(
        [
            str(data.get("headline") or ""),
            str(data.get("body") or ""),
            str(data.get("why_it_matters") or ""),
            str(data.get("uncertainty_note") or ""),
        ]
    )
    if not draft_text.strip():
        issues.append({"code": "quality_loop_error", "message": "Пустой русский текст для ретрансляции."})
    extra_numbers = sorted(_extract_numbers(draft_text) - _extract_numbers(source_text))
    if extra_numbers:
        issues.append({"code": "invented_number", "message": f"В тексте появились числа вне RSS-анонса: {', '.join(extra_numbers[:8])}"})
    if _is_high_risk(topic):
        issues.append({"code": "high_risk_needs_human", "message": "Тема относится к high-risk и требует человека."})
    if _is_poor_rss(topic):
        issues.append({"code": "missing_primary_source", "message": "RSS-анонс слишком бедный для автопубликации."})
    return issues


def _ft_sources(db: Session, channel: Channel) -> list[Source]:
    relay_ids = [int(item) for item in (channel.relay_source_ids or []) if str(item).isdigit()]
    stmt = (
        select(Source)
        .join(SourceChannelMap, SourceChannelMap.source_id == Source.id)
        .where(
            SourceChannelMap.channel_id == channel.id,
            SourceChannelMap.enabled.is_(True),
            Source.status == "active",
            Source.ingestion_enabled.is_(True),
            Source.is_demo.is_(False),
        )
        .order_by(Source.last_poll_at.asc().nullsfirst(), Source.id.asc())
    )
    if relay_ids:
        stmt = stmt.where(Source.id.in_(relay_ids))
    else:
        stmt = stmt.where(Source.url.ilike("%ft.com%"))
    return list(db.execute(stmt).unique().scalars())


def _already_has_post(db: Session, topic: Topic, channel: Channel) -> bool:
    url = _clean_url(topic.url or topic.canonical_url or "")
    if db.scalar(select(Post.id).where(Post.channel_id == channel.id, Post.topic_id == topic.id).limit(1)):
        return True
    if url and db.scalar(select(Post.id).where(Post.channel_id == channel.id, Post.source_urls.contains([url])).limit(1)):
        return True
    return False


def _candidate_topics(db: Session, channel: Channel, source_ids: list[int], *, max_topics: int) -> list[Topic]:
    since = datetime.now(UTC) - timedelta(days=2)
    topics = list(
        db.execute(
            select(Topic)
            .where(
                Topic.is_demo.is_(False),
                Topic.source_id.in_(source_ids),
                Topic.created_at >= since,
                Topic.status.in_(["ready_for_dry_run", "selected", "researched", "edition_selected"]),
                Topic.url != "",
                Topic.assigned_channel_ids.contains([channel.id]),
            )
            .order_by(Topic.source_published_at.desc().nulls_last(), Topic.created_at.desc(), Topic.id.desc())
            .limit(max_topics * 5)
        ).scalars()
    )
    selected: list[Topic] = []
    for topic in topics:
        if _already_has_post(db, topic, channel):
            continue
        selected.append(topic)
        if len(selected) >= max_topics:
            break
    return selected


def _draft_ft_post(db: Session, topic: Topic, channel: Channel) -> tuple[Post, int, int]:
    provider = provider_for_agent(db, "news_editor_agent", manual_override=True)
    url = _clean_url(topic.url or topic.canonical_url or "")
    summary = (topic.summary or topic.raw_text or "").strip()
    prompt_version = str(get_setting(db, "ft_live_prompt_version") or "ft-live-cheap-v1")
    input_payload = {"title": topic.title, "summary": summary, "url": url, "prompt_version": prompt_version}
    data = get_cached_llm_json(
        db,
        source_item_id=topic.source_item_id,
        pipeline_step="ft_live_rewrite",
        prompt_version=prompt_version,
        input_payload=input_payload,
        tokens_saved_estimate=1600,
    )
    response = None
    llm_calls = 0
    tokens_saved = 1600 if data else 0
    if data is None:
        channel_name = channel.name or "Live по-русски"
        prompt = (
            f"Ты редактор отдельного MAX-канала «{channel_name}».\n"
            "Нужно быстро выпустить русский пост по публичному RSS-анонсу выбранного источника.\n"
            "Не обходи paywall и не делай вид, что прочитал полный материал, если есть только title/summary.\n"
            "Не добавляй факты, цифры, даты, цитаты, мотивы, ответственность или причинно-следственные связи вне RSS-анонса.\n"
            "Стиль: коротко, ясно, живо. 2-4 абзаца. Без шаблона «что произошло/почему важно/что дальше».\n"
            "Если данных мало, честно обозначь: «по публичному анонсу Financial Times».\n\n"
            f"TITLE: {topic.title}\nSUMMARY: {summary}\nURL: {url}\n"
        )
        response = provider.generate_structured(
            system_prompt="Return strict JSON. All audience-facing text must be in Russian.",
            user_prompt=prompt,
            output_schema=FT_SCHEMA,
            model=provider.model,
            temperature=0.15,
            max_tokens=900,
            timeout_seconds=75,
        )
        data = response.structured or {}
        llm_calls = 1
        put_cached_llm_json(
            db,
            source_item_id=topic.source_item_id,
            pipeline_step="ft_live_rewrite",
            prompt_version=prompt_version,
            input_payload=input_payload,
            response_json=data,
            provider=response.provider,
            model=response.model,
        )

    title = str(data.get("headline") or topic.title).strip()[:300]
    body = "\n\n".join(
        [
            part
            for part in [
                str(data.get("body") or summary or topic.title).strip(),
                str(data.get("why_it_matters") or "").strip(),
                str(data.get("uncertainty_note") or f"Основано на публичном RSS-анонсе источника для канала «{channel.name}».").strip(),
            ]
            if part
        ]
    )
    issues = _relay_code_guard(topic, data)
    can_auto_publish = bool(get_setting(db, "auto_publish_enabled")) and bool(channel.auto_publish_enabled) and not issues
    post = Post(
        channel_id=channel.id,
        topic_id=topic.id,
        title=title,
        body=body,
        source_urls=public_source_urls([url], limit=1),
        status="approved" if can_auto_publish else "needs_human",
        provider=(response.provider if response else "openai_cache"),
        generation_mode="production_manual",
        model=(response.model if response else "cached"),
        mock_only=False,
        is_demo=False,
        publishable=False,
        non_publishable_reason="FT live relay: approved low-risk posts may publish through guarded MAX path.",
        tokens_input=(response.usage.tokens_input if response else 0),
        tokens_output=(response.usage.tokens_output if response else 0),
        estimated_cost_usd=(response.usage.estimated_cost if response else 0),
        quality_score=86,
        risk_score=65 if issues else 18,
        approved_by="ft_live_monitor" if can_auto_publish else None,
        status_reason="Relay code guard passed." if can_auto_publish else "Relay needs human review.",
        structured_outputs_json={
            "ft_live_mode": True,
            "relay_mode": "single_source_live",
            "cost_optimized": True,
            "llm_calls_count": llm_calls,
            "tokens_saved_estimate": tokens_saved,
            "source_policy": "RSS announcement only; no paywall bypass.",
            "research": {
                "what_happened": title,
                "why_it_matters": data.get("why_it_matters") or "",
                "source_urls": [url],
                "uncertainty": data.get("uncertainty_note") or "Only public RSS announcement was used.",
            },
            "quality_loop": {
                "version": "v1",
                "passed": not issues,
                "blocking_issues": issues,
                "suggested_status": "approved" if can_auto_publish else "needs_human",
                "reason": "Relay code guard passed." if not issues else "Relay code guard requires human review.",
                "relay_code_guard": True,
            },
            "chief_editor_v2": {
                "version": "v1",
                "decision": "approved" if can_auto_publish else "needs_human",
                "reasons": ["Cheap relay code guard. Full newsroom quality loop is intentionally skipped for low-risk relay."],
                "blocking_issues": issues,
                "recommended_fix": "Проверить источник вручную или дождаться более полного RSS-анонса." if issues else "",
                "confidence": 0.78 if not issues else 0.45,
            },
        },
    )
    db.add(post)
    topic.status = "draft_ready" if can_auto_publish else "needs_human"
    db.commit()
    db.refresh(post)
    return post, llm_calls, tokens_saved


def _ft_channel(db: Session, channel_id: int | None = None) -> Channel | None:
    if channel_id is not None:
        return db.get(Channel, channel_id)
    return db.execute(
        select(Channel)
        .where(
            Channel.status == "active",
            (Channel.slug == "financial-times-ru") | (Channel.name.ilike("%Financial Times%")),
        )
        .order_by(Channel.id.desc())
    ).scalar_one_or_none() or db.execute(select(Channel).where(Channel.slug == "era-money")).scalar_one_or_none()


def run_ft_live_monitor(db: Session, *, max_posts: int | None = None, channel_id: int | None = None) -> dict[str, Any]:
    if not bool(get_setting(db, "ft_live_enabled")):
        return {"status": "skipped", "reason": "ft_live_enabled=false", "published": [], "blocked": []}

    channel = _ft_channel(db, channel_id=channel_id)
    if channel is None or channel.status != "active":
        return {"status": "blocked", "reason": "ft_channel_not_active", "published": [], "blocked": []}
    sources = _ft_sources(db, channel)
    if not sources:
        return {"status": "blocked", "reason": "no_active_ft_sources", "published": [], "blocked": []}

    max_posts = max(1, min(int(max_posts or channel.relay_max_posts_per_day or get_setting(db, "ft_live_max_posts_per_run") or 3), 5))
    fetch_limit = max(1, min(int(get_setting(db, "ft_live_items_per_source") or 4), 8))
    fetcher = SourceFetchService()
    scanned: list[dict[str, Any]] = []
    for source in sources:
        result = fetcher.fetch_source(db, source, limit=fetch_limit, create_topics=True)
        scanned.append(result.as_dict())

    topics = _candidate_topics(db, channel, [source.id for source in sources], max_topics=max_posts)
    published: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    llm_calls_count = 0
    tokens_saved_estimate = 0
    for topic in topics:
        try:
            post, llm_calls, saved = _draft_ft_post(db, topic, channel)
            llm_calls_count += llm_calls
            tokens_saved_estimate += saved
            if post.status != "approved":
                blocked.append({"topic_id": topic.id, "post_id": post.id, "title": post.title, "reason": post.status_reason or "needs_human"})
                continue
            try:
                prepare_media_for_post(db, post, generate_fallback=False)
            except Exception as media_exc:
                log_activity(
                    db,
                    actor_type="system",
                    actor_id=None,
                    event_type="ft_live_media_warning",
                    entity_type="post",
                    entity_id=post.id,
                    message=f"FT live media warning for post #{post.id}: {media_exc}",
                    metadata={"error": str(media_exc)[:500]},
                )
            prepare_max_package(db, post)
            db.commit()
            from app.api.routes.posts import MaxPublishRequest, publish_to_max

            publish_to_max(post.id, MaxPublishRequest(confirm=True, note="FT live monitor autopublish."), db)
            published.append({"topic_id": topic.id, "post_id": post.id, "title": post.title})
        except Exception as exc:
            db.rollback()
            blocked.append({"topic_id": topic.id, "title": topic.title, "reason": str(exc)[:500]})
            log_activity(
                db,
                actor_type="system",
                actor_id=None,
                event_type="ft_live_publish_blocked",
                entity_type="topic",
                entity_id=topic.id,
                message=f"FT live publish blocked for topic #{topic.id}: {exc}",
                metadata={"error": str(exc)[:500]},
            )
            db.commit()

    scan_report = zero_token_metadata(
        sources_scanned=len(sources),
        scan=scanned[:10],
        note="RSS/source fetch, dedupe and candidate selection are zero-token. LLM is used only for relay rewrite.",
    )
    report = {
        "status": "completed",
        "sources_scanned": len(sources),
        "candidate_topics_count": len(topics),
        "reason": "Новых уникальных кандидатов нет: RSS проверен, но свежие items уже обработаны или были отфильтрованы как дубли." if not topics else "",
        "published": published,
        "blocked": blocked,
        "llm_calls_count": llm_calls_count,
        "tokens_saved_estimate": tokens_saved_estimate,
        "zero_token_scan": scan_report,
        "scan": scanned[:10],
    }
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="ft_live_monitor_completed",
        entity_type="channel",
        entity_id=channel.id,
        message=f"FT live monitor: published {len(published)}, blocked {len(blocked)}, LLM calls {llm_calls_count}.",
        metadata=report,
    )
    db.commit()
    return report


def run_relay_monitors(db: Session) -> dict[str, Any]:
    if not bool(get_setting(db, "ft_live_enabled")):
        return {"status": "skipped", "reason": "ft_live_enabled=false", "results": []}
    channels = list(
        db.execute(
            select(Channel)
            .where(Channel.status == "active", Channel.channel_mode == "relay", Channel.auto_publish_enabled.is_(True))
            .order_by(Channel.id)
        ).scalars()
    )
    if not channels:
        return {"status": "completed", "results": [run_ft_live_monitor(db)]}
    results = []
    for channel in channels:
        results.append({"channel_id": channel.id, "channel": channel.name, **run_ft_live_monitor(db, channel_id=channel.id)})
    return {"status": "completed", "results": results}
