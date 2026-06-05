from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.contracts import CHIEF_EDITOR_AGENT, EDITOR_AGENT, FACTCHECK_AGENT, RESEARCH_AGENT
from app.db.session import get_db
from app.models.all_models import AgentConfig, OrgAgent, Routine, Task, Topic
from app.services.org import log_activity
from app.services.settings import daily_global_usage, get_settings, update_settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    system_mode: str | None = None
    runtime_mode: str | None = None
    real_newsroom_mode: bool | None = None
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


@router.post("/system/start-editorial-workday")
def start_editorial_workday(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Switch the operator path into safe manual production and reopen stuck draft tasks."""
    next_settings = update_settings(
        db,
        {
            "system_mode": "production_manual",
            "runtime_mode": "LIVE_INTERNAL",
            "real_newsroom_mode": True,
            "global_agents_enabled": False,
            "global_routines_enabled": False,
            "global_publishing_enabled": False,
            "require_human_approval_for_all_posts": True,
            "ui_language": "ru",
            "global_daily_budget_usd": 10.0,
            "global_daily_token_limit": 1_000_000,
        },
    )

    reopened = 0
    cancelled_archived = 0
    tasks = db.execute(
        select(Task).where(
            Task.task_type == "run_topic_pipeline",
            Task.status.in_(["pending", "running", "failed", "waiting_human"]),
        )
    ).scalars().all()
    for task in tasks:
        if task.status == "completed" and (task.payload_json or {}).get("post_id"):
            continue
        topic_id = (task.payload_json or {}).get("topic_id")
        topic = db.get(Topic, topic_id) if topic_id else None
        if topic and topic.status in {"archived", "rejected", "edition_rejected"}:
            task.status = "cancelled"
            task.error_message = f"Topic #{topic.id} is {topic.status}; old generation task cancelled."
            task.locked_at = None
            task.completed_at = None
            cancelled_archived += 1
            continue
        task.status = "pending"
        task.attempts = 0
        task.max_attempts = max(task.max_attempts or 1, 2)
        task.error_message = None
        task.locked_at = None
        task.completed_at = None
        reopened += 1

    editorial_names = [
        "world_scout_agent",
        "factcheck_agent",
        "editor_in_chief",
        "news_editor_agent",
        "food_editor_agent",
        "quality_director",
        "opinion_angle_editor",
    ]
    runtime_names = [RESEARCH_AGENT.name, FACTCHECK_AGENT.name, EDITOR_AGENT.name, CHIEF_EDITOR_AGENT.name]
    org_agents = db.execute(select(OrgAgent).where(OrgAgent.name.in_(editorial_names))).scalars().all()
    for agent in org_agents:
        agent.status = "idle"
        agent.budget_daily = max(agent.budget_daily or 0.0, 25.0)
        agent.token_limit_daily = max(agent.token_limit_daily or 0, 2_000_000)

    configs_updated = 0
    configs = db.execute(
        select(AgentConfig)
        .join(OrgAgent, OrgAgent.id == AgentConfig.org_agent_id)
        .where(OrgAgent.name.in_(editorial_names))
    ).scalars().all()
    openai_model = next((config.model for config in configs if config.provider == "openai" and config.model and config.model != "mock"), None)
    for config in configs:
        config.provider = "openai"
        if openai_model:
            config.model = openai_model
        elif not config.model or config.model == "mock":
            config.model = "gpt-5.5"
        config.enabled = True
        config.max_runs_per_day = max(config.max_runs_per_day or 0, 500)
        config.daily_token_limit = max(config.daily_token_limit or 0, 2_000_000)
        config.daily_budget_usd = max(config.daily_budget_usd or 0.0, 25.0)
        config.timeout_seconds = max(config.timeout_seconds or 0, 90)
        configs_updated += 1

    publisher_agents = db.execute(
        select(OrgAgent).where(
            (OrgAgent.name.ilike("%publisher%")) | (OrgAgent.title.ilike("%publisher%")) | (OrgAgent.role.ilike("%publisher%"))
        )
    ).scalars().all()
    for agent in publisher_agents:
        agent.status = "disabled"
        agent.can_publish = False

    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="editorial_workday_started",
        entity_type="system_settings",
        entity_id=None,
        message="Safe manual editorial workday started. Publishing remains disabled.",
        metadata={
            "reopened_tasks": reopened,
            "cancelled_archived_tasks": cancelled_archived,
            "configs_updated": configs_updated,
            "publisher_agents_disabled": len(publisher_agents),
        },
    )
    db.commit()
    next_settings["daily_usage"] = daily_global_usage(db)
    return {
        "status": "ok",
        "settings": next_settings,
        "reopened_tasks": reopened,
        "cancelled_archived_tasks": cancelled_archived,
        "runtime_agents_ready": runtime_names,
        "configs_updated": configs_updated,
        "publisher_agents_disabled": len(publisher_agents),
        "publishing_enabled": False,
    }


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
