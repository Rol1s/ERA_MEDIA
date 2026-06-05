from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import PlatformChannel, Post
from app.services.editorial_sanitizer import clean_audience_text
from app.services.org import log_activity
from app.services.public_sources import public_source_urls
from app.services.settings import get_setting


MAX_TEXT_LIMIT = 650


def _bold_title(title: str) -> str:
    clean = re.sub(r"\s+", " ", (title or "").strip())
    clean = clean.replace("*", "").replace("_", "")
    return f"**{clean}**" if clean else ""


def _clean_title(title: str) -> str:
    clean = clean_audience_text(title)
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = clean.replace("*", "").replace("_", "")
    return clean[:180].rstrip(" .")


def _is_source_line(line: str) -> bool:
    clean = line.strip()
    return bool(
        re.match(r"(?i)^https?://\S+$", clean)
        or re.match(r"(?i)^источник\s*:", clean)
        or re.match(r"(?i)^source\s*:", clean)
    )


def _strip_trailing_source_block(text: str) -> str:
    lines = [line.rstrip() for line in (text or "").splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    removed = False
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if _is_source_line(last):
            lines.pop()
            removed = True
            continue
        break
    if removed:
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines).strip()


def _clean_body(body: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", clean_audience_text(body))
    text = re.sub(r"(?im)^Редакционная оценка:\s*важно смотреть.*$", "", text)
    brief_headings = [
        "Что произошло",
        "Почему это важно",
        "Что дальше",
        "Какие риски",
        "Кому полезно знать",
        "Что это значит для рынка",
        "Для малого и среднего бизнеса",
        "Вывод",
    ]
    for heading in brief_headings:
        text = re.sub(rf"(?im)^\s*\*{{0,2}}{re.escape(heading)}\s*:?\*{{0,2}}\s*$", "", text)
    text = re.sub(r"(?m)^\s*Деньги\s+—\s+", "", text)
    text = re.sub(r"(?im)^\s*Какие риски\?\s*", "", text)
    text = re.sub(r"(?im)^\s*Кому полезно знать\?\s*", "", text)
    text = re.sub(r"(?m)^\s*\d+\.\s*\*{1,2}[^:\n]{3,90}:\*{1,2}\s*.*$", "", text)
    text = text.replace("**", "").replace("__", "")
    text = _strip_trailing_source_block(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _shorten(text: str, limit: int = MAX_TEXT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    paragraphs = [item.strip() for item in text.split("\n\n") if item.strip()]
    kept: list[str] = []
    total = 0
    for paragraph in paragraphs:
        if total + len(paragraph) + 2 > limit:
            break
        kept.append(paragraph)
        total += len(paragraph) + 2
    if kept:
        return "\n\n".join(kept).strip()
    return text[: limit - 1].rsplit(" ", 1)[0].strip() + "..."


def _source_label(url: str) -> str:
    host = urlparse(url or "").netloc.lower().removeprefix("www.")
    if host.endswith("ft.com"):
        return "Financial Times"
    if host:
        return host
    return url


def _source_block(url: str) -> str:
    return ""


def _channel_url(db: Session, post: Post) -> str:
    platform = db.execute(
        select(PlatformChannel).where(
            PlatformChannel.channel_id == post.channel_id,
            PlatformChannel.platform == "max",
        )
    ).scalar_one_or_none()
    return (platform.external_channel_url if platform else "") or ""


def build_max_buttons(db: Session, post: Post) -> dict[str, Any]:
    suggest_url = str(get_setting(db, "submission_bot_url") or get_setting(db, "owner_bot_public_url") or "").strip()
    subscribe_url = _channel_url(db, post)
    source_url = ""
    sources = public_source_urls(post.source_urls, limit=1)
    if sources and re.match(r"(?i)^https?://", sources[0]):
        source_url = sources[0]
    buttons: list[dict[str, str]] = []
    if source_url:
        buttons.append({"text": "Подробнее", "url": source_url})
    if suggest_url:
        buttons.append({"text": "Предложить новость", "url": suggest_url})
    if subscribe_url and re.match(r"(?i)^https?://", subscribe_url):
        buttons.append({"text": "Подписаться на канал", "url": subscribe_url})
    return {
        "buttons": buttons,
        "cta_links": {
            "source_url": source_url,
            "suggest_news_url": suggest_url,
            "subscribe_url": subscribe_url,
        },
        "rendering": "stored_for_max_ui_and_manual_review",
    }


def prepare_max_package(db: Session, post: Post) -> Post:
    sources = public_source_urls(post.source_urls, limit=3)
    body = _shorten(_clean_body(post.body))
    parts = [_bold_title(_clean_title(post.title)), body]
    buttons = build_max_buttons(db, post)
    post.max_packaged_text = "\n\n".join([part for part in parts if part]).strip()
    post.max_buttons_json = buttons
    post.operator_checklist_json = {
        "language": "ru",
        "rss_xml_hidden": len(sources) != len(post.source_urls or []),
        "needs_human_approval": True,
        "media_status": post.media_status or "missing",
        "media_first": True,
        "high_risk": bool((post.risk_score or 0) >= 60),
        "checks": [
            "Проверить заголовок и первые две строки.",
            "Проверить источник: RSS/XML не должны быть видны читателю.",
            "Проверить факт, оценку и риск.",
            "Проверить медиа: картинка не должна выглядеть как доказательство, если она сгенерирована.",
        ],
    }
    log_activity(
        db,
        actor_type="agent",
        actor_id=None,
        event_type="max_package_prepared",
        entity_type="post",
        entity_id=post.id,
        message=f"MAX package prepared for post #{post.id}.",
        metadata={"length": len(post.max_packaged_text), "buttons": buttons, "media_first": True},
    )
    return post


def max_text_for_publish(db: Session, post: Post) -> str:
    if not (post.max_packaged_text or "").strip():
        prepare_max_package(db, post)
    return (post.max_packaged_text or "").strip()
