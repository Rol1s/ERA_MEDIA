from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import PipelineError
from app.db.session import get_db
from app.models.all_models import Channel, DailyEdition
from app.services import daily_editions as editions

router = APIRouter()


class ApproveFinalPackRequest(BaseModel):
    human_note: str = ""


class EditorNotesRequest(BaseModel):
    editor_notes: str = ""


@router.get("", response_model=None)
def list_editions(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    editions.ensure_today_editions(db)
    rows = db.execute(select(DailyEdition).order_by(DailyEdition.date.desc(), DailyEdition.id.desc())).scalars().all()
    return [editions.edition_payload(db, row) for row in rows]


@router.post("/today", response_model=None)
def create_today_editions(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = editions.ensure_today_editions(db)
    return [editions.edition_payload(db, row) for row in rows]


@router.post("/today/{channel_slug}", response_model=None)
def create_today_edition(channel_slug: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    if channel_slug not in editions.EDITION_CHANNELS:
        raise HTTPException(status_code=422, detail="Step 2.8A supports only ERA AI and ERA Деньги")
    channel = db.execute(select(Channel).where(Channel.slug == channel_slug)).scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return editions.edition_payload(db, editions.ensure_daily_edition(db, channel))


@router.get("/{edition_id}", response_model=None)
def get_edition(edition_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    return editions.edition_detail_payload(db, edition)


@router.patch("/{edition_id}", response_model=None)
def update_notes(edition_id: int, payload: EditorNotesRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    edition.editor_notes = payload.editor_notes
    db.commit()
    db.refresh(edition)
    return editions.edition_payload(db, edition)


@router.post("/{edition_id}/collect", response_model=None)
def collect(edition_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    return editions.collect_candidates(db, edition)


@router.post("/{edition_id}/select-top", response_model=None)
def select_top(edition_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    topics = editions.select_top_topics(db, edition)
    return {"edition": editions.edition_payload(db, edition), "selected_topic_ids": [topic.id for topic in topics]}


@router.post("/{edition_id}/topics/{topic_id}/select", response_model=None)
def select_topic(edition_id: int, topic_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    try:
        topic = editions.select_topic(db, edition, topic_id)
        return {"topic_id": topic.id, "status": topic.status, "edition": editions.edition_payload(db, edition)}
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{edition_id}/topics/{topic_id}/reject", response_model=None)
def reject_topic(edition_id: int, topic_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    try:
        topic = editions.reject_topic(db, edition, topic_id)
        return {"topic_id": topic.id, "status": topic.status, "edition": editions.edition_payload(db, edition)}
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{edition_id}/topics/{topic_id}/generate-post", response_model=None)
def generate_post(edition_id: int, topic_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    try:
        post = editions.generate_post_for_topic(db, edition, topic_id)
        return {"post_id": post.id, "post_status": post.status, "edition": editions.edition_payload(db, edition)}
    except (PipelineError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{edition_id}/posts/{post_id}/regenerate", response_model=None)
def regenerate_post(edition_id: int, post_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    try:
        post = editions.regenerate_post_once(db, edition, post_id)
        return {"post_id": post.id, "post_status": post.status, "edition": editions.edition_payload(db, edition)}
    except (PipelineError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{edition_id}/posts/{post_id}/approve-final", response_model=None)
def approve_final(edition_id: int, post_id: int, payload: ApproveFinalPackRequest | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    try:
        post = editions.approve_post_for_final_pack(db, edition, post_id, human_note=(payload.human_note if payload else ""))
        return {"post_id": post.id, "post_status": post.status, "edition": editions.edition_payload(db, edition)}
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{edition_id}/posts/{post_id}/reject", response_model=None)
def reject_post(edition_id: int, post_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    edition = db.get(DailyEdition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    try:
        post = editions.reject_post_for_edition(db, edition, post_id)
        return {"post_id": post.id, "post_status": post.status, "edition": editions.edition_payload(db, edition)}
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
