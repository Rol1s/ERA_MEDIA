from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import PipelineError, approve_post, reject_post, request_post_rewrite, schedule_post
from app.db.session import get_db
from app.models.all_models import Post
from app.schemas.post import PostCreate, PostRead, PostUpdate
from app.services.org import log_activity

router = APIRouter()


class ScheduleRequest(BaseModel):
    scheduled_at: datetime | None = None


class RewriteRequest(BaseModel):
    notes: list[str] = Field(default_factory=lambda: ["make_more_useful"])


@router.get("", response_model=list[PostRead])
def list_posts(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[Post]:
    stmt = select(Post).order_by(Post.created_at.desc())
    if status_filter:
        stmt = stmt.where(Post.status == status_filter)
    return list(db.execute(stmt).scalars())


@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, db: Session = Depends(get_db)) -> Post:
    data = payload.model_dump()
    if data.get("generation_mode") in {"mock", "dry_run"}:
        data["publishable"] = False
        data["non_publishable_reason"] = data.get("non_publishable_reason") or (
            "Mock content is not publishable"
            if data.get("generation_mode") == "mock"
            else "Dry-run content requires human review and cannot be publicly published"
        )
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
    return post


@router.patch("/{post_id}", response_model=PostRead)
def update_post(post_id: int, payload: PostUpdate, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    data = payload.model_dump(exclude_unset=True)
    editable_fields = {"title", "body", "source_urls", "visual_prompt", "visual_url", "status_reason", "risk_reason", "quality_reason"}
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
        "structured_outputs_json",
        "published_at",
        "max_message_id",
    }
    data = {key: value for key, value in data.items() if key not in protected_fields}
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
