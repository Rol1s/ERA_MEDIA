from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import AgentRun, Post
from app.schemas.agent_run import AgentRunCreate, AgentRunRead

router = APIRouter()


def _matches_topic(run: AgentRun, topic_id: int) -> bool:
    return run.input_json.get("topic_id") == topic_id or run.output_json.get("topic_id") == topic_id


@router.get("", response_model=list[AgentRunRead])
def list_agent_runs(
    topic_id: int | None = Query(default=None),
    post_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AgentRun]:
    runs = list(db.execute(select(AgentRun).order_by(AgentRun.started_at.desc())).scalars())
    if post_id is not None:
        post = db.get(Post, post_id)
        if post is None:
            raise HTTPException(status_code=404, detail="Post not found")
        runs = [
            run
            for run in runs
            if run.input_json.get("post_id") == post_id
            or run.output_json.get("post_id") == post_id
            or (post.topic_id is not None and _matches_topic(run, post.topic_id))
        ]
    if topic_id is not None:
        runs = [run for run in runs if _matches_topic(run, topic_id)]
    return runs


@router.post("", response_model=AgentRunRead, status_code=status.HTTP_201_CREATED)
def create_agent_run(payload: AgentRunCreate, db: Session = Depends(get_db)) -> AgentRun:
    run = AgentRun(**payload.model_dump())
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/{agent_run_id}", response_model=AgentRunRead)
def get_agent_run(agent_run_id: int, db: Session = Depends(get_db)) -> AgentRun:
    run = db.get(AgentRun, agent_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


@router.delete("/{agent_run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_run(agent_run_id: int, db: Session = Depends(get_db)) -> None:
    run = db.get(AgentRun, agent_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    db.delete(run)
    db.commit()
