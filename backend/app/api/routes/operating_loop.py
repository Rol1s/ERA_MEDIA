from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import OperatingLoopRun
from app.services.operating_loop import AgentOperatingLoop

router = APIRouter(prefix="/operating-loop")


class OperatingLoopRequest(BaseModel):
    action: str
    mode: str = "manual_run"


def operating_loop_payload(run: OperatingLoopRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "mode": run.mode,
        "action": run.action,
        "planning_only": run.planning_only,
        "status": run.status,
        "report_json": run.report_json,
        "issues_created": run.issues_created,
        "issues_updated": run.issues_updated,
        "issues_moved": run.issues_moved,
        "decisions_made": run.decisions_made,
        "warnings_json": run.warnings_json,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error_message": run.error_message,
    }


@router.post("/run", response_model=None)
def run_operating_loop(payload: OperatingLoopRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        run = AgentOperatingLoop(db).run(action=payload.action, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return operating_loop_payload(run)


@router.get("/latest", response_model=None)
def latest_operating_loop(db: Session = Depends(get_db)) -> dict[str, Any] | None:
    run = db.execute(select(OperatingLoopRun).order_by(OperatingLoopRun.started_at.desc(), OperatingLoopRun.id.desc())).scalars().first()
    return operating_loop_payload(run) if run else None
