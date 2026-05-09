from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import PipelineError, run_real_dry_run_pipeline, run_topic_pipeline
from app.db.session import get_db
from app.models.all_models import Topic
from app.schemas.post import PostRead
from app.schemas.topic import TopicCreate, TopicRead, TopicUpdate
from app.services.org import log_activity

router = APIRouter()


@router.get("", response_model=list[TopicRead])
def list_topics(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[Topic]:
    stmt = select(Topic).order_by(Topic.created_at.desc())
    if status_filter:
        stmt = stmt.where(Topic.status == status_filter)
    return list(db.execute(stmt).scalars())


@router.post("", response_model=TopicRead, status_code=status.HTTP_201_CREATED)
def create_topic(payload: TopicCreate, db: Session = Depends(get_db)) -> Topic:
    topic = Topic(**payload.model_dump())
    db.add(topic)
    db.flush()
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="topic_created",
        entity_type="topic",
        entity_id=topic.id,
        message=f"Topic created: {topic.title}",
    )
    db.commit()
    db.refresh(topic)
    return topic


@router.get("/{topic_id}", response_model=TopicRead)
def get_topic(topic_id: int, db: Session = Depends(get_db)) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.patch("/{topic_id}", response_model=TopicRead)
def update_topic(topic_id: int, payload: TopicUpdate, db: Session = Depends(get_db)) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(topic, key, value)
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="topic_updated",
        entity_type="topic",
        entity_id=topic.id,
        message=f"Topic updated: {topic.title}",
        metadata={"fields": list(data.keys()), "status": topic.status},
    )
    db.commit()
    db.refresh(topic)
    return topic


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, db: Session = Depends(get_db)) -> None:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    db.delete(topic)
    db.commit()


@router.post("/{topic_id}/generate-draft", response_model=PostRead)
def generate_draft(topic_id: int, channel_id: int | None = None, db: Session = Depends(get_db)):
    try:
        return run_topic_pipeline(db, topic_id=topic_id, channel_id=channel_id, manual_override=True)
    except (PipelineError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{topic_id}/run-pipeline", response_model=PostRead)
def run_pipeline(topic_id: int, channel_id: int | None = None, db: Session = Depends(get_db)):
    try:
        return run_topic_pipeline(db, topic_id=topic_id, channel_id=channel_id, manual_override=True)
    except (PipelineError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{topic_id}/run-dry-run", response_model=PostRead)
def run_dry_run(topic_id: int, channel_id: int | None = None, db: Session = Depends(get_db)):
    try:
        return run_real_dry_run_pipeline(db, topic_id=topic_id, channel_id=channel_id)
    except (PipelineError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
