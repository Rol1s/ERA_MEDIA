from __future__ import annotations

import json
import mimetypes
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.orchestrator import PipelineError, approve_post, reject_post, request_post_rewrite, run_real_dry_run_pipeline
from app.db.session import SessionLocal, get_db
from app.models.all_models import ActivityEvent, EditorialDirectorMessage, EditorialDirectorSession, NewsroomSubmission, Post, Source, Task, Topic
from app.services.morning_source_scan import MorningSourceScanService
from app.services.org import log_activity
from app.services.public_sources import public_source_urls
from app.services.secrets import SecretStoreError, resolve_secret_value
from app.services.senior_journalist_briefing import SeniorJournalistBriefingService
from app.services.settings import get_setting, update_settings
from app.services.visual_media import local_media_path

router = APIRouter(prefix="/owner-bot")

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_SECRET_NAME = "TELEGRAM_BOT_TOKEN"


class OwnerBotSettingsUpdate(BaseModel):
    enabled: bool | None = None
    allowed_chat_id: str | None = None


class SetWebhookRequest(BaseModel):
    public_base_url: str


class SendTestRequest(BaseModel):
    text: str = "ERA Media Factory: бот владельца подключен."


def _resolve_telegram_token(db: Session) -> str:
    try:
        return resolve_secret_value(db, "telegram", TELEGRAM_SECRET_NAME)
    except SecretStoreError as exc:
        raise HTTPException(status_code=422, detail="TELEGRAM_BOT_TOKEN не настроен в интеграциях.") from exc


def _telegram_call(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram {method} failed: HTTP {exc.code} {body[:500]}") from exc


def _telegram_send_file(token: str, method: str, payload: dict[str, Any], file_field: str, file_path: str) -> dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"
    boundary = f"----era{secrets.token_hex(12)}"
    chunks: list[bytes] = []
    for key, value in payload.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(file_path, "rb") as handle:
        file_bytes = handle.read()
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode())
    chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram {method} failed: HTTP {exc.code} {body_text[:500]}") from exc


def _telegram_get_updates(token: str, offset: int) -> list[dict[str, Any]]:
    url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates"
    payload = {"offset": offset, "timeout": 20, "allowed_updates": ["message", "edited_message"]}
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8") or "{}")
    if not body.get("ok"):
        raise RuntimeError(f"Telegram getUpdates failed: {body}")
    return list(body.get("result") or [])


def _send_message(db: Session, chat_id: str | int, text: str) -> None:
    token = _resolve_telegram_token(db)
    _telegram_call(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text[:3900],
            "disable_web_page_preview": True,
        },
    )


def _send_photo(db: Session, chat_id: str | int, image_path: str, caption: str = "") -> None:
    token = _resolve_telegram_token(db)
    _telegram_send_file(
        token,
        "sendPhoto",
        {"chat_id": chat_id, "caption": caption[:1000]},
        "photo",
        image_path,
    )


class _ThreadBackgroundTasks:
    def add_task(self, func: Any, *args: Any, **kwargs: Any) -> None:
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()


def _set_value(db: Session, key: str, value: Any) -> None:
    update_settings(db, {key: value})


def _owner_allowed(db: Session, chat_id: str) -> bool:
    return bool(get_setting(db, "owner_bot_enabled")) and str(get_setting(db, "owner_bot_allowed_chat_id") or "") == str(chat_id)


def _incoming_message(update: dict[str, Any]) -> tuple[str, str]:
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    text = str(message.get("text") or message.get("caption") or "").strip()
    return chat_id, text


def _create_public_submission(db: Session, update: dict[str, Any], chat_id: str) -> int:
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    text = str(message.get("text") or message.get("caption") or "").strip()
    url_match = re.search(r"https?://\S+", text)
    photo = message.get("photo") or []
    media_url = str(photo[-1].get("file_id")) if photo else ""
    name = " ".join([str(sender.get("first_name") or ""), str(sender.get("last_name") or "")]).strip() or str(chat.get("username") or "")
    item = NewsroomSubmission(
        source="telegram",
        submitter_chat_id=chat_id,
        submitter_name=name,
        text=text,
        url=(url_match.group(0).rstrip(").,;") if url_match else ""),
        media_url=media_url,
        raw_payload_json=update,
    )
    db.add(item)
    db.flush()
    log_activity(
        db,
        actor_type="audience",
        actor_id=None,
        event_type="submission_created",
        entity_type="submission",
        entity_id=item.id,
        message=f"Audience submission #{item.id} received from Telegram.",
        metadata={"chat_id": chat_id, "has_media": bool(media_url)},
    )
    db.commit()
    return item.id


def _latest_activity(db: Session) -> str:
    event = db.execute(select(ActivityEvent).order_by(ActivityEvent.created_at.desc()).limit(1)).scalar_one_or_none()
    if not event:
        return "Событий пока нет."
    return f"{event.created_at:%d.%m %H:%M}: {event.message}"


def _latest_task(db: Session) -> str:
    task = db.execute(select(Task).order_by(Task.updated_at.desc()).limit(1)).scalar_one_or_none()
    if not task:
        return "Задач пока нет."
    return f"#{task.id} {task.task_type}: {task.status}"


def _post_line(post: Post) -> str:
    return f"#{post.id} [{post.status}] {post.title[:120]}"


def _topic_line(topic: Topic) -> str:
    score = int(topic.final_score or topic.importance_score or topic.freshness_score or 0)
    return f"#{topic.id} {score}/100 {topic.title[:120]}"


def _status_text(db: Session) -> str:
    pending = db.scalar(select(func.count()).select_from(Post).where(Post.status.in_(["draft", "needs_review", "approved"]))) or 0
    published = db.scalar(select(func.count()).select_from(Post).where(Post.status == "published")) or 0
    fresh = db.scalar(
        select(func.count())
        .select_from(Topic)
        .where(Topic.created_at >= datetime.now(UTC) - timedelta(hours=24), Topic.status.not_in(["archived", "rejected"]))
    ) or 0
    return "\n".join(
        [
            "ERA Media Factory",
            f"Режим: {get_setting(db, 'system_mode')}",
            f"Тем за 24 часа: {fresh}",
            f"Постов в работе: {pending}",
            f"Опубликовано всего: {published}",
            f"Задача: {_latest_task(db)}",
            f"Событие: {_latest_activity(db)}",
        ]
    )


def _radar_text(db: Session, limit: int = 10) -> str:
    topics = list(
        db.execute(
            select(Topic)
            .join(Topic.source, isouter=True)
            .where(
                Topic.is_demo.is_(False),
                Topic.status.not_in(["archived", "rejected"]),
                Topic.created_at >= datetime.now(UTC) - timedelta(hours=36),
            )
            .order_by(Topic.final_score.desc(), Topic.importance_score.desc(), Topic.freshness_score.desc(), Topic.created_at.desc())
            .limit(limit)
        ).scalars()
    )
    if not topics:
        return "В радаре нет свежих тем. Запусти /scan."
    lines = ["Свежий радар:"]
    lines += [_topic_line(topic) for topic in topics]
    lines.append("\nКоманды: /draft <topic_id>, /watch <topic_id>, /reject_topic <topic_id>")
    return "\n".join(lines)


def _posts_text(db: Session, limit: int = 10) -> str:
    posts = list(
        db.execute(
            select(Post)
            .where(Post.is_demo.is_(False), Post.mock_only.is_(False), Post.provider != "mock", Post.generation_mode != "mock")
            .order_by(Post.created_at.desc())
            .limit(limit)
        ).scalars()
    )
    if not posts:
        return "Постов пока нет. Запусти /radar, затем /draft <topic_id>."
    lines = ["Последние посты:"]
    lines += [_post_line(post) for post in posts]
    lines.append("\nКоманды: /post <id>, /approve <id>, /publish <id>, /rewrite <id> <правка>, /reject <id>")
    return "\n".join(lines)


def _post_text(db: Session, post_id: int) -> str:
    post = db.get(Post, post_id)
    if post is None:
        return f"Пост #{post_id} не найден."
    sources = "\n".join(public_source_urls(post.source_urls, limit=4))
    return "\n".join(
        [
            _post_line(post),
            f"Качество: {post.quality_score}/100, риск: {post.risk_score}/100",
            "",
            post.body[:2400],
            "",
            f"Источники:\n{sources}" if sources else "Источники не указаны.",
        ]
    )


def _send_post_preview(db: Session, chat_id: str, post_id: int) -> str:
    post = db.get(Post, post_id)
    if post is None:
        return f"Пост #{post_id} не найден."
    image_path = local_media_path(post.image_url)
    if image_path is not None:
        _send_photo(db, chat_id, str(image_path), f"#{post.id} {post.title}")
    return _post_text(db, post_id)


def _latest_briefing_text(db: Session) -> str:
    session = db.execute(
        select(EditorialDirectorSession)
        .where(EditorialDirectorSession.mode == "journalist_briefing")
        .order_by(EditorialDirectorSession.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if session is None:
        return "Редакционной повестки ещё нет. Запусти /agenda."
    message = db.execute(
        select(EditorialDirectorMessage)
        .where(EditorialDirectorMessage.session_id == session.id, EditorialDirectorMessage.role == "assistant")
        .order_by(EditorialDirectorMessage.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    content = (message.content if message else session.summary) or "Повестка готова."
    return f"Повестка #{session.id} [{session.status}]\n\n{content[:3300]}"


def _run_scan_and_reply(chat_id: str, max_sources: int = 200) -> None:
    db = SessionLocal()
    try:
        result = MorningSourceScanService(db).run(max_sources=max_sources, limit_per_source=3)
        db.commit()
        _send_message(
            db,
            chat_id,
            "Радар обновлён.\n"
            f"Источников: {result.get('sources_scanned', 0)}\n"
            f"Новых материалов: {result.get('new_source_items', 0)}\n"
            f"Новых тем: {result.get('new_topics', 0)}\n\n"
            "Дальше: /radar или /agenda",
        )
    except Exception as exc:
        db.rollback()
        _send_message(db, chat_id, f"Сбор радара упал: {exc}")
    finally:
        db.close()


def _run_agenda_and_reply(chat_id: str) -> None:
    db = SessionLocal()
    try:
        result = SeniorJournalistBriefingService(db).run(max_items=160, target_topics=15)
        db.commit()
        text = (result.get("messages") or [{}])[-1].get("content") or result.get("summary") or "Повестка готова."
        _send_message(db, chat_id, f"Редакционная повестка готова.\n\n{text[:3300]}\n\nДальше: /draft <topic_id> или /posts")
    except Exception as exc:
        db.rollback()
        _send_message(db, chat_id, f"Повестка упала: {exc}")
    finally:
        db.close()


def _run_draft_and_reply(chat_id: str, topic_id: int) -> None:
    db = SessionLocal()
    try:
        post = run_real_dry_run_pipeline(db, topic_id=topic_id, channel_id=None)
        log_activity(db, actor_type="human", actor_id=None, event_type="owner_bot_draft_created", entity_type="post", entity_id=post.id, message=f"Owner bot created draft for topic #{topic_id}.")
        db.commit()
        _send_message(db, chat_id, f"Черновик готов: {_post_line(post)}\n\nПроверить: /post {post.id}\nОдобрить: /approve {post.id}")
    except Exception as exc:
        db.rollback()
        _send_message(db, chat_id, f"Черновик по теме #{topic_id} не создан: {exc}")
    finally:
        db.close()


def _handle_command(db: Session, chat_id: str, text: str, background_tasks: BackgroundTasks) -> str:
    parts = text.strip().split()
    command = parts[0].lower() if parts else "/help"
    arg = parts[1] if len(parts) > 1 else ""
    rest = " ".join(parts[2:]).strip()

    if command in {"/start", "/help"}:
        return (
            "Я пульт владельца ERA Media Factory.\n\n"
            "/status — состояние редакции\n"
            "/scan — собрать свежие источники\n"
            "/radar — показать свежие темы\n"
            "/agenda — собрать редакционную повестку\n"
            "/brief — показать последнюю повестку\n"
            "/draft <topic_id> — написать черновик\n"
            "/posts — последние посты\n"
            "/post <id> — открыть пост\n"
            "/approve <id> — одобрить\n"
            "/publish <id> — опубликовать в MAX\n"
            "/rewrite <id> <задача> — переписать\n"
            "/reject <id> — отклонить"
        )
    if command == "/status":
        return _status_text(db)
    if command == "/scan":
        background_tasks.add_task(_run_scan_and_reply, chat_id)
        return "Запустил сбор радара. Напишу сюда, когда закончу."
    if command == "/radar":
        return _radar_text(db)
    if command == "/agenda":
        background_tasks.add_task(_run_agenda_and_reply, chat_id)
        return "Собираю редакционную повестку. Это может занять несколько минут."
    if command == "/brief":
        return _latest_briefing_text(db)
    if command == "/posts":
        return _posts_text(db)
    if command == "/post" and arg.isdigit():
        return _send_post_preview(db, chat_id, int(arg))
    if command == "/draft" and arg.isdigit():
        background_tasks.add_task(_run_draft_and_reply, chat_id, int(arg))
        return f"Запустил написание черновика по теме #{arg}. Сообщу, когда пост появится."
    if command == "/approve" and arg.isdigit():
        post = approve_post(db, int(arg), approved_by="telegram_owner")
        db.commit()
        return f"Одобрено: {_post_line(post)}\nПубликация: /publish {post.id}"
    if command == "/publish" and arg.isdigit():
        from app.api.routes.posts import MaxPublishRequest, publish_to_max

        post = publish_to_max(int(arg), MaxPublishRequest(confirm=True, note="Опубликовано владельцем через Telegram-бота."), db)
        return f"Опубликовано в MAX: {_post_line(post)}"
    if command == "/reject" and arg.isdigit():
        post = reject_post(db, int(arg))
        db.commit()
        return f"Отклонено: {_post_line(post)}"
    if command == "/rewrite" and arg.isdigit():
        post = request_post_rewrite(db, int(arg), notes=[rest or "Сделать живее, короче и сильнее."])
        db.commit()
        return f"Переписано: {_post_line(post)}\nПроверить: /post {post.id}"
    if command == "/watch" and arg.isdigit():
        topic = db.get(Topic, int(arg))
        if topic is None:
            return f"Тема #{arg} не найдена."
        topic.status = "watching"
        log_activity(db, actor_type="human", actor_id=None, event_type="owner_bot_topic_watch", entity_type="topic", entity_id=topic.id, message=f"Owner bot put topic #{topic.id} on watch.")
        db.commit()
        return f"Поставил на наблюдение: {_topic_line(topic)}"
    if command == "/reject_topic" and arg.isdigit():
        topic = db.get(Topic, int(arg))
        if topic is None:
            return f"Тема #{arg} не найдена."
        topic.status = "rejected"
        log_activity(db, actor_type="human", actor_id=None, event_type="owner_bot_topic_rejected", entity_type="topic", entity_id=topic.id, message=f"Owner bot rejected topic #{topic.id}.")
        db.commit()
        return f"Отклонил тему: {_topic_line(topic)}"
    return "Не понял команду. Напиши /help."


@router.get("/status", response_model=None)
def owner_bot_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        "enabled": get_setting(db, "owner_bot_enabled"),
        "allowed_chat_id": get_setting(db, "owner_bot_allowed_chat_id"),
        "has_webhook_secret": bool(get_setting(db, "owner_bot_webhook_secret")),
        "text": _status_text(db),
    }


@router.patch("/settings", response_model=None)
def update_owner_bot_settings(payload: OwnerBotSettingsUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if payload.enabled is not None:
        values["owner_bot_enabled"] = payload.enabled
    if payload.allowed_chat_id is not None:
        values["owner_bot_allowed_chat_id"] = payload.allowed_chat_id.strip()
    if values:
        update_settings(db, values)
    return owner_bot_status(db)


@router.post("/telegram/set-webhook", response_model=None)
def set_telegram_webhook(payload: SetWebhookRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    token = _resolve_telegram_token(db)
    secret = str(get_setting(db, "owner_bot_webhook_secret") or "")
    if not secret:
        secret = secrets.token_urlsafe(32)
        _set_value(db, "owner_bot_webhook_secret", secret)
    base = payload.public_base_url.rstrip("/")
    url = f"{base}/api/owner-bot/telegram/webhook?secret={urllib.parse.quote(secret)}"
    result = _telegram_call(token, "setWebhook", {"url": url, "drop_pending_updates": True})
    log_activity(db, actor_type="human", actor_id=None, event_type="owner_bot_webhook_set", entity_type="integration", entity_id=None, message="Telegram owner bot webhook set.", metadata={"public_base_url": base})
    db.commit()
    return {"ok": bool(result.get("ok")), "result": result, "webhook_url": url}


@router.post("/telegram/send-test", response_model=None)
def send_telegram_test(payload: SendTestRequest | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    chat_id = str(get_setting(db, "owner_bot_allowed_chat_id") or "")
    if not chat_id:
        raise HTTPException(status_code=422, detail="owner_bot_allowed_chat_id не настроен. Напишите боту /start и возьмите chat_id из ответа.")
    _send_message(db, chat_id, (payload or SendTestRequest()).text)
    return {"ok": True, "chat_id": chat_id}


@router.post("/telegram/webhook", response_model=None)
def telegram_webhook(
    update: dict[str, Any],
    background_tasks: BackgroundTasks,
    secret: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    expected = str(get_setting(db, "owner_bot_webhook_secret") or "")
    if not expected or not secrets.compare_digest(secret, expected):
        raise HTTPException(status_code=403, detail="Bad owner bot webhook secret")
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    text = str(message.get("text") or "").strip()
    if not chat_id or not text:
        return {"ok": True, "ignored": True}
    if not _owner_allowed(db, chat_id):
        submission_id = _create_public_submission(db, update, chat_id)
        _send_message(db, chat_id, f"Спасибо. Редакция получила вашу новость, номер предложки #{submission_id}.")
        return {"ok": True, "authorized": False, "submission_id": submission_id}
    try:
        reply = _handle_command(db, chat_id, text, background_tasks)
    except (PipelineError, HTTPException, RuntimeError, ValueError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        reply = f"Команда не выполнена: {detail}"
        db.rollback()
    _send_message(db, chat_id, reply)
    return {"ok": True}


@router.post("/telegram/poll-once", response_model=None)
def telegram_poll_once(db: Session = Depends(get_db)) -> dict[str, Any]:
    token = _resolve_telegram_token(db)
    offset = int(get_setting(db, "owner_bot_update_offset") or 0)
    updates = _telegram_get_updates(token, offset)
    processed = 0
    for update in updates:
        next_offset = int(update.get("update_id", 0)) + 1
        _set_value(db, "owner_bot_update_offset", max(next_offset, int(get_setting(db, "owner_bot_update_offset") or 0)))
        chat_id, text = _incoming_message(update)
        if not chat_id or not text:
            continue
        if not _owner_allowed(db, chat_id):
            submission_id = _create_public_submission(db, update, chat_id)
            _send_message(db, chat_id, f"Спасибо. Редакция получила вашу новость, номер предложки #{submission_id}.")
            processed += 1
            continue
        try:
            reply = _handle_command(db, chat_id, text, _ThreadBackgroundTasks())  # type: ignore[arg-type]
        except (PipelineError, HTTPException, RuntimeError, ValueError) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            reply = f"Команда не выполнена: {detail}"
            db.rollback()
        _send_message(db, chat_id, reply)
        processed += 1
    return {"ok": True, "updates": len(updates), "processed": processed, "offset": get_setting(db, "owner_bot_update_offset")}


_poller_started = False


def _owner_bot_poll_loop() -> None:
    while True:
        db = SessionLocal()
        try:
            try:
                token = resolve_secret_value(db, "telegram", TELEGRAM_SECRET_NAME)
            except Exception:
                time.sleep(10)
                continue
            offset = int(get_setting(db, "owner_bot_update_offset") or 0)
            updates = _telegram_get_updates(token, offset)
            for update in updates:
                next_offset = int(update.get("update_id", 0)) + 1
                _set_value(db, "owner_bot_update_offset", max(next_offset, int(get_setting(db, "owner_bot_update_offset") or 0)))
                chat_id, text = _incoming_message(update)
                if not chat_id or not text:
                    continue
                if not _owner_allowed(db, chat_id):
                    submission_id = _create_public_submission(db, update, chat_id)
                    _send_message(db, chat_id, f"Спасибо. Редакция получила вашу новость, номер предложки #{submission_id}.")
                    continue
                try:
                    reply = _handle_command(db, chat_id, text, _ThreadBackgroundTasks())  # type: ignore[arg-type]
                    _send_message(db, chat_id, reply)
                except Exception as exc:
                    db.rollback()
                    _send_message(db, chat_id, f"Команда не выполнена: {exc}")
        except Exception:
            time.sleep(10)
        finally:
            db.close()
        time.sleep(2)


def start_owner_bot_poller() -> None:
    global _poller_started
    if _poller_started or os.getenv("OWNER_BOT_POLLER_DISABLED", "").lower() in {"1", "true", "yes"}:
        return
    _poller_started = True
    thread = threading.Thread(target=_owner_bot_poll_loop, name="owner-bot-poller", daemon=True)
    thread.start()
