from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import NewsroomSubmission, Topic
from app.schemas.topic import TopicRead
from app.services.org import log_activity

router = APIRouter(prefix="/submissions")


class SubmissionCreate(BaseModel):
    source: str = "manual"
    submitter_chat_id: str = ""
    submitter_name: str = ""
    text: str = ""
    url: str = ""
    media_url: str = ""
    raw_payload_json: dict[str, Any] = Field(default_factory=dict)


class SubmissionReject(BaseModel):
    reason: str = ""


def _extract_url(text: str) -> str:
    match = re.search(r"https?://\S+", text or "")
    return match.group(0).rstrip(").,;") if match else ""


def _title_from_submission(item: NewsroomSubmission) -> str:
    text = (item.text or "").strip()
    if not text:
        return "Предложенная новость"
    line = text.splitlines()[0].strip()
    return line[:180] or "Предложенная новость"


@router.get("", response_model=None)
def list_submissions(status: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    stmt = select(NewsroomSubmission).order_by(NewsroomSubmission.created_at.desc())
    if status:
        stmt = stmt.where(NewsroomSubmission.status == status)
    return [
        {
            "id": item.id,
            "status": item.status,
            "source": item.source,
            "submitter_chat_id": item.submitter_chat_id,
            "submitter_name": item.submitter_name,
            "text": item.text,
            "url": item.url,
            "media_url": item.media_url,
            "topic_id": item.topic_id,
            "rejected_reason": item.rejected_reason,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in db.execute(stmt).scalars()
    ]


@router.post("", response_model=None)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    text = payload.text.strip()
    url = payload.url.strip() or _extract_url(text)
    item = NewsroomSubmission(
        source=payload.source.strip() or "manual",
        submitter_chat_id=payload.submitter_chat_id.strip(),
        submitter_name=payload.submitter_name.strip(),
        text=text,
        url=url,
        media_url=payload.media_url.strip(),
        raw_payload_json=payload.raw_payload_json,
    )
    db.add(item)
    db.flush()
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="submission_created",
        entity_type="submission",
        entity_id=item.id,
        message=f"News submission #{item.id} created.",
        metadata={"source": item.source, "url": item.url},
    )
    db.commit()
    return {"id": item.id, "status": item.status}


@router.post("/{submission_id}/create-topic", response_model=TopicRead)
def create_topic_from_submission(submission_id: int, db: Session = Depends(get_db)) -> Topic:
    item = db.get(NewsroomSubmission, submission_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if item.status not in {"new", "reviewing"}:
        raise HTTPException(status_code=422, detail="Submission is already processed")
    topic = Topic(
        title=_title_from_submission(item),
        url=item.url or None,
        raw_text=item.text,
        summary=item.text[:900],
        detected_at=datetime.now(UTC),
        freshness_score=50,
        relevance_score=0.6,
        usefulness_score=0.6,
        originality_score=0.5,
        source_trust_score=0.35,
        risk_score=0.3,
        final_score=55,
        why_this_matters="Предложка аудитории: нужно проверить источник и редакционную ценность.",
        suggested_angle="Проверить факт, найти первоисточник и решить, есть ли человеческий конфликт или практическая польза.",
        status="ready_for_dry_run",
        extraction_status="user_submission",
        language="ru",
        freshness_status="fresh",
        freshness_reason="Новость предложена аудиторией; требует проверки редактором.",
        content_type="news_update",
        assigned_channel_ids=[],
    )
    db.add(topic)
    db.flush()
    item.status = "topic_created"
    item.topic_id = topic.id
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="submission_topic_created",
        entity_type="submission",
        entity_id=item.id,
        message=f"Submission #{item.id} converted to topic #{topic.id}.",
        metadata={"topic_id": topic.id},
    )
    db.commit()
    db.refresh(topic)
    return topic


@router.post("/{submission_id}/reject", response_model=None)
def reject_submission(submission_id: int, payload: SubmissionReject | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(NewsroomSubmission, submission_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    item.status = "rejected"
    item.rejected_reason = (payload.reason if payload else "") or "Отклонено редактором"
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="submission_rejected",
        entity_type="submission",
        entity_id=item.id,
        message=f"Submission #{item.id} rejected.",
        metadata={"reason": item.rejected_reason},
    )
    db.commit()
    return {"id": item.id, "status": item.status}
