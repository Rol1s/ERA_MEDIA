import json
import os
import re
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import PipelineError, approve_post, reject_post, request_post_rewrite, schedule_post
from app.db.session import get_db
from app.models.all_models import Channel, Integration, PlatformChannel, Post
from app.schemas.post import PostCreate, PostRead, PostUpdate
from app.services.org import log_activity
from app.services.max_packaging import max_text_for_publish, prepare_max_package
from app.services.media_producer import prepare_media_for_post
from app.services.editorial_quality_loop import run_quality_loop, validate_post_quality_for_approval
from app.services.public_sources import public_source_urls
from app.services.secrets import resolve_secret_value
from app.services.settings import get_setting
from app.services.visual_media import generate_visual_for_post, local_media_path, upload_image_to_max

router = APIRouter()
MAX_DEFAULT_BASE_URL = "https://platform-api.max.ru"


class ScheduleRequest(BaseModel):
    scheduled_at: datetime | None = None


class RewriteRequest(BaseModel):
    notes: list[str] = Field(default_factory=lambda: ["make_more_useful"])


class ManualPublishRequest(BaseModel):
    channel: str = ""
    published_at: datetime | None = None
    published_url: str = ""
    note: str = ""


class MaxPublishRequest(BaseModel):
    confirm: bool = False
    note: str = ""


def _max_text(post: Post) -> str:
    source_lines = public_source_urls(post.source_urls, limit=5)
    sources = "\n".join([f"Источник: {url}" for url in source_lines[:5]])
    return f"{post.title.strip()}\n\n{post.body.strip()}\n\n{sources}".strip()


def _send_max_message(*, base_url: str, token: str, chat_id: str, text: str) -> dict:
    url = f"{base_url.rstrip('/')}/messages?chat_id={urllib.parse.quote(str(chat_id), safe='')}"
    data = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body or "{}")
            return {"ok": True, "status": response.status, "body": parsed}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "body": body[:1200]}


def _send_max_message_with_attachment(*, base_url: str, token: str, chat_id: str, text: str, attachment: dict) -> dict:
    url = f"{base_url.rstrip('/')}/messages?chat_id={urllib.parse.quote(str(chat_id), safe='')}"
    data = json.dumps({"text": text, "attachments": [attachment]}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body or "{}")
            return {"ok": True, "status": response.status, "body": parsed}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "body": body[:1200]}


def _send_max_payload(*, base_url: str, token: str, chat_id: str, text: str, attachments: list[dict] | None = None) -> dict:
    url = f"{base_url.rstrip('/')}/messages?chat_id={urllib.parse.quote(str(chat_id), safe='')}"
    payload: dict[str, object] = {"text": text, "format": "markdown"}
    if attachments:
        payload["attachments"] = attachments
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body or "{}")
            return {"ok": True, "status": response.status, "body": parsed}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "body": body[:1200]}


def _max_inline_keyboard(post: Post) -> dict | None:
    buttons = ((post.max_buttons_json or {}).get("buttons") or []) if isinstance(post.max_buttons_json, dict) else []
    rows = []
    for button in buttons:
        text = str(button.get("text") or "").strip()
        url = str(button.get("url") or "").strip()
        if text and re.match(r"(?i)^https?://", url):
            rows.append([{"type": "link", "text": text[:64], "url": url}])
    if not rows:
        return None
    return {"type": "inline_keyboard", "payload": {"buttons": rows}}


def _extract_max_message_id(body: dict) -> str:
    for key in ("message_id", "id", "mid"):
        if body.get(key):
            return str(body[key])
    message = body.get("message")
    if isinstance(message, dict):
        for key in ("message_id", "id", "mid"):
            if message.get(key):
                return str(message[key])
        nested_body = message.get("body")
        if isinstance(nested_body, dict):
            for key in ("message_id", "id", "mid"):
                if nested_body.get(key):
                    return str(nested_body[key])
    nested_body = body.get("body")
    if isinstance(nested_body, dict):
        for key in ("message_id", "id", "mid"):
            if nested_body.get(key):
                return str(nested_body[key])
    return ""


def _sanitize_post_media(post: Post) -> None:
    if post.image_url and local_media_path(post.image_url) is None:
        post.image_url = None
        post.visual_url = None
        post.media_status = "missing"
        post.media_source_type = "none"
        post.media_source_url = ""
        post.image_generation_status = "missing_file"


@router.post("/{post_id}/generate-visual", response_model=PostRead)
def generate_visual(post_id: int, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        generate_visual_for_post(db, post)
        db.commit()
        db.refresh(post)
        return post
    except Exception as exc:
        post.image_generation_status = "failed"
        log_activity(
            db,
            actor_type="agent",
            actor_id=None,
            event_type="visual_generation_failed",
            entity_type="post",
            entity_id=post.id,
            message=f"Visual generation failed for post #{post.id}: {exc}",
            metadata={"error": str(exc)[:500]},
        )
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{post_id}/prepare-media", response_model=PostRead)
def prepare_media(post_id: int, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        prepare_media_for_post(db, post, generate_fallback=True)
        db.commit()
        db.refresh(post)
        return post
    except Exception as exc:
        post.media_status = "failed"
        post.media_rights_note = str(exc)[:1000]
        log_activity(
            db,
            actor_type="agent",
            actor_id=None,
            event_type="media_prepare_failed",
            entity_type="post",
            entity_id=post.id,
            message=f"Media Producer failed for post #{post.id}: {exc}",
            metadata={"error": str(exc)[:500]},
        )
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{post_id}/prepare-max-package", response_model=PostRead)
def prepare_max_package_endpoint(post_id: int, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    prepare_max_package(db, post)
    db.commit()
    db.refresh(post)
    return post


@router.post("/{post_id}/quality-check", response_model=PostRead)
def quality_check(post_id: int, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    run_quality_loop(db, post)
    db.commit()
    db.refresh(post)
    return post


@router.get("", response_model=list[PostRead])
def list_posts(
    status_filter: str | None = Query(default=None, alias="status"),
    channel_id: int | None = Query(default=None),
    show_archived: bool = False,
    show_mock_demo: bool = False,
    include_relay: bool = False,
    db: Session = Depends(get_db),
) -> list[Post]:
    stmt = select(Post).order_by(Post.created_at.desc())
    if not include_relay:
        stmt = stmt.join(Channel, Channel.id == Post.channel_id).where(Channel.channel_mode != "relay")
    if status_filter:
        stmt = stmt.where(Post.status == status_filter)
    if channel_id:
        stmt = stmt.where(Post.channel_id == channel_id)
    if not show_archived:
        stmt = stmt.where(Post.status.notin_(["archived", "edition_rejected", "rejected"]))
    if not show_mock_demo:
        stmt = stmt.where(Post.is_demo.is_(False), Post.mock_only.is_(False), Post.provider != "mock", Post.generation_mode != "mock")
    posts = list(db.execute(stmt).scalars())
    changed = False
    for post in posts:
        before = post.image_url
        _sanitize_post_media(post)
        changed = changed or before != post.image_url
    if changed:
        db.commit()
    return posts


@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, db: Session = Depends(get_db)) -> Post:
    data = payload.model_dump()
    if get_setting(db, "real_newsroom_mode"):
        raise HTTPException(status_code=422, detail="Real Newsroom Mode blocks manual/mock post creation. Use real source -> topic -> OpenAI dry-run.")
    if data.get("generation_mode") in {"mock", "dry_run"}:
        data["publishable"] = False
        data["non_publishable_reason"] = data.get("non_publishable_reason") or (
            "Mock content is not publishable"
            if data.get("generation_mode") == "mock"
            else "Dry-run content requires human review and cannot be publicly published"
        )
    if "source_urls" in data:
        data["source_urls"] = public_source_urls(data.get("source_urls"), limit=10)
    post = Post(**data)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.get("/{post_id}", response_model=PostRead)
def get_post(post_id: int, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    before = post.image_url
    _sanitize_post_media(post)
    if before != post.image_url:
        db.commit()
    return post


@router.patch("/{post_id}", response_model=PostRead)
def update_post(post_id: int, payload: PostUpdate, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    data = payload.model_dump(exclude_unset=True)
    editable_fields = {"title", "body", "source_urls", "visual_prompt", "visual_url", "status_reason", "risk_reason", "quality_reason", "max_packaged_text"}
    protected_fields = {
        "mock_only",
        "generation_mode",
        "provider",
        "model",
        "prompt_template_version",
        "publishable",
        "non_publishable_reason",
        "not_publishable_reason",
        "tokens_input",
        "tokens_output",
        "estimated_cost_usd",
        "llm_trace_id",
        "published_at",
        "published_url",
        "manual_publish_note",
        "max_message_id",
    }
    data = {key: value for key, value in data.items() if key not in protected_fields}
    if "source_urls" in data:
        data["source_urls"] = public_source_urls(data.get("source_urls"), limit=10)
    if editable_fields.intersection(data):
        history = list(post.version_history or [])
        history.append(
            {
                "version": post.version,
                "title": post.title,
                "body": post.body,
                "source_urls": post.source_urls,
                "visual_prompt": post.visual_prompt,
                "changed_at": datetime.now().isoformat(),
                "reason": "manual_edit",
            }
        )
        post.version_history = history
        post.version += 1
        if post.structured_outputs_json and post.structured_outputs_json.get("quality_loop"):
            loop = dict(post.structured_outputs_json.get("quality_loop") or {})
            loop["passed"] = False
            loop["suggested_status"] = "needs_human"
            loop["reason"] = "manual_edit_requires_quality_check"
            loop["blocking_issues"] = [
                {
                    "code": "quality_loop_error",
                    "message": "После ручной правки нужно заново запустить quality-check.",
                    "severity": "blocker",
                    "claim": "",
                    "recommended_fix": "Нажать «Проверить смысл» перед одобрением/публикацией.",
                }
            ]
            post.structured_outputs_json = {**post.structured_outputs_json, "quality_loop": loop}
    for key, value in data.items():
        setattr(post, key, value)
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="post_edited",
        entity_type="post",
        entity_id=post.id,
        message=f"Post #{post.id} edited manually.",
        metadata={"fields": list(data.keys()), "version": post.version},
    )
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: Session = Depends(get_db)) -> None:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()


@router.post("/{post_id}/approve", response_model=PostRead)
def approve(post_id: int, db: Session = Depends(get_db)) -> Post:
    try:
        return approve_post(db, post_id)
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{post_id}/reject", response_model=PostRead)
def reject(post_id: int, db: Session = Depends(get_db)) -> Post:
    try:
        return reject_post(db, post_id)
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{post_id}/archive", response_model=PostRead)
def archive(post_id: int, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    post.status = "archived"
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="post_archived",
        entity_type="post",
        entity_id=post.id,
        message=f"Post #{post.id} archived.",
        metadata={"mock_only": post.mock_only},
    )
    db.commit()
    db.refresh(post)
    return post


@router.post("/{post_id}/rewrite", response_model=PostRead)
def rewrite(post_id: int, payload: RewriteRequest | None = None, db: Session = Depends(get_db)) -> Post:
    try:
        return request_post_rewrite(db, post_id, notes=(payload.notes if payload else None))
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{post_id}/schedule", response_model=PostRead)
def schedule(post_id: int, payload: ScheduleRequest | None = None, db: Session = Depends(get_db)) -> Post:
    try:
        return schedule_post(db, post_id, scheduled_at=(payload.scheduled_at if payload else None))
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{post_id}/unschedule", response_model=PostRead)
def unschedule(post_id: int, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != "scheduled":
        raise HTTPException(status_code=422, detail="Only scheduled posts can be unscheduled")
    post.status = "approved"
    post.scheduled_at = None
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="post_unscheduled",
        entity_type="post",
        entity_id=post.id,
        message=f"Post #{post.id} unscheduled.",
    )
    db.commit()
    db.refresh(post)
    return post


@router.post("/{post_id}/mark-published-manually", response_model=PostRead)
def mark_published_manually_endpoint(post_id: int, payload: ManualPublishRequest, db: Session = Depends(get_db)) -> Post:
    from app.services.launch import mark_published_manually

    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        return mark_published_manually(db, post, published_at=payload.published_at, published_url=payload.published_url, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{post_id}/publish-max", response_model=PostRead)
def publish_to_max(post_id: int, payload: MaxPublishRequest, db: Session = Depends(get_db)) -> Post:
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="Human confirmation is required for MAX publish")
    if not bool(get_setting(db, "global_publishing_enabled")):
        raise HTTPException(status_code=422, detail="MAX publishing is disabled by global publishing switch")
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.max_message_id or post.status == "published":
        raise HTTPException(status_code=422, detail="Post is already published")
    if post.mock_only or post.is_demo or post.provider == "mock" or post.generation_mode == "mock":
        raise HTTPException(status_code=422, detail="Mock/demo content cannot be published to MAX")
    if post.status not in {"approved", "final_pack", "ready_for_manual_copy"}:
        raise HTTPException(status_code=422, detail="Post must be approved by human before MAX publishing")
    if not post.source_urls:
        raise HTTPException(status_code=422, detail="Post must have source URLs before MAX publishing")
    try:
        validate_post_quality_for_approval(post)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if local_media_path(post.image_url) is None:
        try:
            prepare_media_for_post(db, post, generate_fallback=True)
            db.flush()
        except Exception as exc:
            log_activity(
                db,
                actor_type="system",
                actor_id=None,
                event_type="max_media_prepare_failed",
                entity_type="post",
                entity_id=post.id,
                message=f"MAX media preparation failed for post #{post.id}: {exc}",
                metadata={"error": str(exc)[:500]},
            )
            db.commit()
            raise HTTPException(status_code=502, detail=f"MAX media preparation failed: {exc}") from exc
    if local_media_path(post.image_url) is None:
        raise HTTPException(status_code=422, detail="MAX post requires media before publishing")
    visual_generation = (post.structured_outputs_json or {}).get("visual_generation") or {}
    if post.image_generation_status == "local_fallback_ready" or visual_generation.get("provider") == "local_fallback":
        raise HTTPException(
            status_code=422,
            detail="MAX post has only local fallback media; replace with source preview or approved generated image before publishing",
        )

    text = max_text_for_publish(db, post)
    if len(text) > 4000:
        raise HTTPException(status_code=422, detail=f"MAX text is too long: {len(text)} chars. Shorten to 4000 chars or less.")

    platform = db.execute(
        select(PlatformChannel).where(
            PlatformChannel.channel_id == post.channel_id,
            PlatformChannel.platform == "max",
        )
    ).scalar_one_or_none()
    if platform is None or platform.status != "connected" or not platform.external_chat_id:
        raise HTTPException(status_code=422, detail="MAX channel is not connected for this ERA channel")

    integration = db.get(Integration, platform.integration_id) if platform.integration_id else db.execute(select(Integration).where(Integration.provider == "max")).scalar_one_or_none()
    base_url = ((integration.config_json or {}).get("MAX_API_BASE_URL") if integration else None) or MAX_DEFAULT_BASE_URL
    try:
        token = resolve_secret_value(db, "max", (integration.secret_ref if integration else "") or "MAX_BOT_TOKEN")
    except Exception:
        token = os.getenv((integration.secret_ref if integration else "") or "MAX_BOT_TOKEN") or ""
    if not token:
        raise HTTPException(status_code=422, detail="MAX bot token is missing")

    attachment = None
    image_path = local_media_path(post.image_url)
    if image_path is not None:
        try:
            uploaded = upload_image_to_max(base_url=base_url, token=token, image_path=image_path)
            attachment = {"type": "image", "payload": uploaded}
        except Exception as exc:
            log_activity(
                db,
                actor_type="system",
                actor_id=None,
                event_type="max_image_upload_failed",
                entity_type="post",
                entity_id=post.id,
                message=f"MAX image upload failed for post #{post.id}: {exc}",
                metadata={"error": str(exc)[:500]},
            )
            db.commit()
            raise HTTPException(status_code=502, detail=f"MAX image upload failed: {exc}") from exc

    attachments = []
    if attachment:
        attachments.append(attachment)
    keyboard = _max_inline_keyboard(post)
    if keyboard:
        attachments.append(keyboard)
    result = _send_max_payload(base_url=base_url, token=token, chat_id=platform.external_chat_id, text=text, attachments=attachments)
    if not result["ok"] and keyboard:
        fallback_attachments = [item for item in attachments if item is not keyboard]
        log_activity(
            db,
            actor_type="system",
            actor_id=None,
            event_type="max_keyboard_failed_retry_without_buttons",
            entity_type="post",
            entity_id=post.id,
            message=f"MAX inline keyboard failed for post #{post.id}; retrying without buttons.",
            metadata={"status": result.get("status"), "body": result.get("body")},
        )
        db.flush()
        result = _send_max_payload(base_url=base_url, token=token, chat_id=platform.external_chat_id, text=text, attachments=fallback_attachments)
    if not result["ok"]:
        log_activity(
            db,
            actor_type="system",
            actor_id=None,
            event_type="max_publish_failed",
            entity_type="post",
            entity_id=post.id,
            message=f"MAX publish failed for post #{post.id}: HTTP {result.get('status')}",
            metadata={"status": result.get("status"), "body": result.get("body")},
        )
        db.commit()
        raise HTTPException(status_code=502, detail=f"MAX publish failed: HTTP {result.get('status')} {result.get('body')}")

    body = result.get("body") or {}
    post.status = "published"
    post.published_at = datetime.now(UTC)
    post.published_url = platform.external_channel_url
    post.manual_publish_note = payload.note or "Published to MAX by explicit human button."
    post.max_message_id = _extract_max_message_id(body) or str(body.get("recipient", {}).get("chat_id", ""))
    post.publishable = False
    post.non_publishable_reason = "Already published to MAX."
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="max_post_published",
        entity_type="post",
        entity_id=post.id,
        message=f"Post #{post.id} published to MAX channel #{platform.channel_id}.",
        metadata={"platform_channel_id": platform.id, "chat_id": platform.external_chat_id, "max_message_id": post.max_message_id, "auto_publish": False, "image_url": post.image_url, "with_image": bool(attachment)},
    )
    db.commit()
    db.refresh(post)
    return post
