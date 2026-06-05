from __future__ import annotations

import mimetypes
import re
import urllib.parse
import urllib.request
import uuid
from html import unescape
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.all_models import Post
from app.services.org import log_activity
from app.services.public_sources import public_source_urls
from app.services.visual_media import MEDIA_ROOT, MEDIA_URL_PREFIX, generate_visual_for_post, local_media_path


USER_AGENT = "ERA Media Factory MediaProducer/1.0"
IMAGE_MAX_BYTES = 8 * 1024 * 1024
HIGH_RISK_MEDIA_TERMS = {
    "война",
    "удар",
    "атака",
    "дрон",
    "беспилот",
    "взрыв",
    "пожар",
    "эвакуац",
    "погиб",
    "ранен",
    "смерт",
    "дет",
    "суд",
    "криминал",
    "медицин",
    "здоров",
    "политик",
    "санкц",
    "обвин",
    "ответствен",
}


def _official_source(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(marker in host for marker in [".gov", ".mil", "mchs", "who.int", "un.org", "nasa.gov", "kremlin.ru"])


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(request, timeout=20) as response:
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type and "xml" not in content_type and "text" not in content_type:
            return ""
        return response.read(900_000).decode("utf-8", errors="replace")


def _tag_attrs(tag: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, _, value in re.findall(r"([:\w-]+)\s*=\s*([\"'])(.*?)\2", tag, flags=re.IGNORECASE | re.DOTALL):
        attrs[key.lower()] = unescape(value.strip())
    return attrs


def _looks_like_image_url(url: str) -> bool:
    clean = url.lower()
    path = urllib.parse.urlparse(clean).path
    return path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")) or any(
        marker in clean for marker in ["image", "photo", "thumb", "thumbnail", "preview", "og"]
    )


def _find_preview_image(html: str, base_url: str) -> str:
    for tag in re.findall(r"<meta\b[^>]*>", html, flags=re.IGNORECASE | re.DOTALL):
        attrs = _tag_attrs(tag)
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key in {"og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"}:
            content = attrs.get("content", "")
            if content:
                return urllib.parse.urljoin(base_url, content)

    for tag in re.findall(r"<link\b[^>]*>", html, flags=re.IGNORECASE | re.DOTALL):
        attrs = _tag_attrs(tag)
        rel = (attrs.get("rel") or "").lower()
        href = attrs.get("href", "")
        if href and "image_src" in rel:
            return urllib.parse.urljoin(base_url, href)

    for tag in re.findall(r"<(?:media:content|media:thumbnail|enclosure)\b[^>]*>", html, flags=re.IGNORECASE | re.DOTALL):
        attrs = _tag_attrs(tag)
        url = attrs.get("url", "")
        media_type = (attrs.get("type") or attrs.get("medium") or "").lower()
        if url and ("image" in media_type or _looks_like_image_url(url)):
            return urllib.parse.urljoin(base_url, url)

    return ""


def _download_image(url: str, post_id: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.5"})
    with urllib.request.urlopen(request, timeout=35) as response:
        content_type = response.headers.get("Content-Type", "")
        if "image" not in content_type:
            raise RuntimeError(f"Preview is not an image: {content_type}")
        data = response.read(IMAGE_MAX_BYTES + 1)
        if len(data) > IMAGE_MAX_BYTES:
            raise RuntimeError("Preview image is too large")
    ext = mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) or Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
    if ext.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"source-post-{post_id}-{uuid.uuid4().hex[:10]}{ext}"
    path = MEDIA_ROOT / filename
    path.write_bytes(data)
    return f"{MEDIA_URL_PREFIX}/{filename}"


def _is_high_risk_media_post(post: Post) -> bool:
    haystack = f"{post.title or ''}\n{post.body or ''}\n{post.risk_reason or ''}".lower()
    return (post.risk_score or 0) >= 60 or any(term in haystack for term in HIGH_RISK_MEDIA_TERMS)


def _rich_media_layout(post: Post, *, source_found: bool, generated: bool = False) -> str:
    text = f"{post.title or ''}\n{post.body or ''}".lower()
    if source_found:
        return "source_hero"
    if any(term in text for term in ["карта", "район", "область", "город", "границ", "маршрут"]):
        return "editorial_map_card"
    if any(term in text for term in ["несколько", "серия", "подборка", "дайджест"]):
        return "collage_or_grid"
    return "editorial_card" if generated else "manual_media_required"


def _store_rich_media_plan(
    post: Post,
    *,
    status: str,
    layout: str,
    source_type: str,
    source_url: str = "",
    reason: str = "",
    generated_allowed: bool = False,
) -> None:
    data: dict[str, Any] = dict(post.structured_outputs_json or {})
    data["rich_media"] = {
        "version": "v1",
        "status": status,
        "layout": layout,
        "source_type": source_type,
        "source_url": source_url,
        "generated_allowed": generated_allowed,
        "media_first": True,
        "max_format": "image_or_video_on_top_then_bold_headline_and_short_text",
        "safety_rule": (
            "Generated media is editorial illustration only and must never be presented as evidence."
            if generated_allowed
            else "Use real source/official media or manual review; do not generate fake event evidence."
        ),
        "reason": reason,
    }
    post.structured_outputs_json = data


def prepare_media_for_post(db: Session, post: Post, *, generate_fallback: bool = True) -> Post:
    if local_media_path(post.image_url) is not None:
        post.media_status = post.media_status if post.media_status != "missing" else "approved"
        post.media_source_type = post.media_source_type if post.media_source_type != "none" else "manual"
        _store_rich_media_plan(
            post,
            status=post.media_status or "approved",
            layout="source_hero" if post.media_source_type in {"source_preview", "official"} else "manual_hero",
            source_type=post.media_source_type or "manual",
            source_url=post.media_source_url or post.image_url or "",
            reason="У поста уже есть локальный медиафайл.",
            generated_allowed=post.media_source_type == "generated",
        )
        return post

    errors: list[str] = []
    high_risk_media = _is_high_risk_media_post(post)
    for source_url in public_source_urls(post.source_urls, limit=3):
        try:
            html = _fetch_text(source_url)
            preview = _find_preview_image(html, source_url)
            if not preview:
                continue
            image_url = _download_image(preview, post.id)
            post.image_url = image_url
            post.visual_url = image_url
            post.media_source_type = "official" if _official_source(source_url) else "source_preview"
            post.media_source_url = preview
            post.media_status = "needs_review" if (post.risk_score or 0) >= 60 else "found"
            post.media_rights_note = (
                "Найдено preview-изображение на странице источника. Перед публикацией проверьте, что оно не вводит в заблуждение и допустимо как превью."
            )
            post.image_generation_status = "source_preview_found"
            _store_rich_media_plan(
                post,
                status=post.media_status,
                layout="source_hero",
                source_type=post.media_source_type,
                source_url=preview,
                reason="Используем реальное preview-изображение из источника: медиа сверху, затем короткий MAX-текст.",
                generated_allowed=False,
            )
            log_activity(
                db,
                actor_type="agent",
                actor_id=None,
                event_type="media_preview_found",
                entity_type="post",
                entity_id=post.id,
                message=f"Media Producer found source preview for post #{post.id}.",
                metadata={"source_url": source_url, "preview_url": preview, "image_url": image_url},
            )
            return post
        except Exception as exc:
            errors.append(f"{source_url}: {exc}")

    if high_risk_media:
        try:
            generate_visual_for_post(db, post)
            post.media_source_type = "generated"
            post.media_source_url = post.image_url or ""
            post.media_status = "needs_review"
            post.media_rights_note = (
                "Сгенерирована безопасная редакционная карточка: не фото события, не доказательство, без реалистичных жертв/политиков/сцен удара. "
                "Если источник даёт реальное фото или видео, редактор может заменить карточку вручную."
            )
            _store_rich_media_plan(
                post,
                status=post.media_status,
                layout=_rich_media_layout(post, source_found=False, generated=True),
                source_type="generated",
                source_url=post.image_url or "",
                reason="Высокорисковая тема без найденного preview; создана безопасная абстрактная редакционная карточка вместо фальшивого фото события.",
                generated_allowed=True,
            )
            log_activity(
                db,
                actor_type="agent",
                actor_id=None,
                event_type="media_generated_high_risk_editorial_card",
                entity_type="post",
                entity_id=post.id,
                message=f"Media Producer generated safe editorial card for high-risk post #{post.id}.",
                metadata={"errors": errors[-3:], "risk_score": post.risk_score},
            )
            return post
        except Exception as exc:
            errors.append(f"high-risk editorial card: {exc}")
        post.media_status = "needs_review"
        post.media_source_type = "none"
        post.media_source_url = ""
        post.image_generation_status = "source_media_required"
        post.media_rights_note = (
            "Высокорисковая новость без найденного реального медиа. Нужна ручная картинка/видео/карта из источника или официального канала. "
            "Сгенерированную картинку нельзя подавать как доказательство события."
        )
        _store_rich_media_plan(
            post,
            status="needs_review",
            layout="manual_media_required",
            source_type="none",
            reason="Тема рискованная, а реальное медиа не найдено. Генерация отключена, чтобы не создать фальшивое визуальное доказательство.",
            generated_allowed=False,
        )
        log_activity(
            db,
            actor_type="agent",
            actor_id=None,
            event_type="media_manual_review_required",
            entity_type="post",
            entity_id=post.id,
            message=f"Media Producer requires manual source media for high-risk post #{post.id}.",
            metadata={"errors": errors[-3:], "risk_score": post.risk_score},
        )
        return post

    if generate_fallback:
        generate_visual_for_post(db, post)
        post.media_source_type = "generated"
        post.media_source_url = post.image_url or ""
        post.media_status = "generated"
        post.media_rights_note = "Сгенерированная редакционная карточка. Это не фото события и не доказательство."
        _store_rich_media_plan(
            post,
            status=post.media_status,
            layout=_rich_media_layout(post, source_found=False, generated=True),
            source_type="generated",
            source_url=post.image_url or "",
            reason="Реальное preview не найдено; для низкорисковой темы создана редакционная карточка.",
            generated_allowed=True,
        )
        log_activity(
            db,
            actor_type="agent",
            actor_id=None,
            event_type="media_generated_fallback",
            entity_type="post",
            entity_id=post.id,
            message=f"Media Producer generated fallback visual for post #{post.id}.",
            metadata={"errors": errors[-3:]},
        )
        return post

    post.media_status = "failed" if errors else "missing"
    post.media_rights_note = "; ".join(errors[-3:])
    _store_rich_media_plan(
        post,
        status=post.media_status,
        layout="manual_media_required",
        source_type="none",
        reason=post.media_rights_note or "Медиа не найдено.",
        generated_allowed=False,
    )
    return post
