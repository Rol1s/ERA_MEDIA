from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import OrgAgent, Routine
from app.services.org import log_activity
from app.services.settings import daily_global_usage, get_settings, update_settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    system_mode: str | None = None
    global_agents_enabled: bool | None = None
    global_routines_enabled: bool | None = None
    global_publishing_enabled: bool | None = None
    global_daily_budget_usd: float | None = None
    global_daily_token_limit: int | None = None
    require_human_approval_for_all_posts: bool | None = None
    ui_language: str | None = None
    usd_to_rub_rate: float | None = None
    admin_notification_provider: str | None = None
    admin_notification_target: str | None = None
    notify_on_review_needed: bool | None = None
    notify_on_failure: bool | None = None
    notify_on_budget_warning: bool | None = None


@router.get("/settings")
def read_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = get_settings(db)
    settings["daily_usage"] = daily_global_usage(db)
    return settings


@router.patch("/settings")
def patch_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        values = payload.model_dump(exclude_unset=True)
        next_settings = update_settings(db, values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="settings_updated",
        entity_type="system_settings",
        entity_id=None,
        message="System safety settings updated.",
        metadata=values,
    )
    db.commit()
    next_settings["daily_usage"] = daily_global_usage(db)
    return next_settings


@router.post("/system/pause-agents")
def pause_all_agents(db: Session = Depends(get_db)) -> dict[str, int]:
    agents = db.execute(select(OrgAgent).where(OrgAgent.agent_type != "human")).scalars().all()
    count = 0
    for agent in agents:
        if agent.status != "disabled":
            agent.status = "paused"
            count += 1
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="agents_paused_all",
        entity_type="org_agent",
        entity_id=None,
        message="All non-disabled agents paused.",
        metadata={"count": count},
    )
    db.commit()
    return {"paused": count}


@router.post("/system/pause-routines")
def pause_all_routines(db: Session = Depends(get_db)) -> dict[str, int]:
    routines = db.execute(select(Routine)).scalars().all()
    for routine in routines:
        routine.enabled = False
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="routines_paused_all",
        entity_type="routine",
        entity_id=None,
        message="All routines disabled.",
        metadata={"count": len(routines)},
    )
    db.commit()
    return {"disabled": len(routines)}
