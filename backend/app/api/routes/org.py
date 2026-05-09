from datetime import UTC, datetime, time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import ActivityEvent, Channel, CostEvent, Goal, OrgAgent, Routine, Task
from app.services.org import daily_agent_usage, log_activity
from app.services.settings import get_settings

router = APIRouter()


class AgentStatusRequest(BaseModel):
    status: str


class RoutineUpdateRequest(BaseModel):
    enabled: bool | None = None
    cron_schedule: str | None = None
    max_runs_per_day: int | None = None
    max_budget_per_run: float | None = None


def today_start() -> datetime:
    return datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)


def agent_payload(db: Session, agent: OrgAgent) -> dict[str, Any]:
    usage = daily_agent_usage(db, agent.id)
    budget_warning = (agent.budget_daily > 0 and float(usage["cost"]) >= agent.budget_daily * 0.8) or (
        agent.token_limit_daily > 0 and int(usage["tokens"]) >= agent.token_limit_daily * 0.8
    )
    return {
        "id": agent.id,
        "name": agent.name,
        "title": agent.title,
        "role": agent.role,
        "agent_type": agent.agent_type,
        "parent_agent_id": agent.parent_agent_id,
        "description": agent.description,
        "responsibilities": agent.responsibilities,
        "supervises": agent.supervises,
        "reviewed_by": agent.reviewed_by,
        "can_create_tasks": agent.can_create_tasks,
        "can_approve_posts": agent.can_approve_posts,
        "can_publish": agent.can_publish,
        "can_spend_budget": agent.can_spend_budget,
        "permissions_json": agent.permissions_json,
        "budget_daily": agent.budget_daily,
        "budget_monthly": agent.budget_monthly,
        "token_limit_daily": agent.token_limit_daily,
        "status": agent.status,
        "heartbeat_enabled": agent.heartbeat_enabled,
        "heartbeat_cron": agent.heartbeat_cron,
        "last_heartbeat_at": agent.last_heartbeat_at,
        "daily_cost_used": usage["cost"],
        "daily_tokens_used": usage["tokens"],
        "budget_warning": budget_warning,
    }


def goal_payload(goal: Goal) -> dict[str, Any]:
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "owner_agent_id": goal.owner_agent_id,
        "target_metric": goal.target_metric,
        "target_value": goal.target_value,
        "current_value": goal.current_value,
        "status": goal.status,
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
    }


def routine_payload(routine: Routine) -> dict[str, Any]:
    return {
        "id": routine.id,
        "name": routine.name,
        "description": routine.description,
        "owner_agent_id": routine.owner_agent_id,
        "cron_schedule": routine.cron_schedule,
        "task_type": routine.task_type,
        "payload_json": routine.payload_json,
        "enabled": routine.enabled,
        "max_runs_per_day": routine.max_runs_per_day,
        "max_budget_per_run": routine.max_budget_per_run,
        "last_run_status": routine.last_run_status,
        "last_run_at": routine.last_run_at,
        "next_run_at": routine.next_run_at,
        "created_at": routine.created_at,
        "updated_at": routine.updated_at,
    }


def activity_payload(event: ActivityEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "message": event.message,
        "metadata_json": event.metadata_json,
        "created_at": event.created_at,
    }


def task_payload(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "payload_json": task.payload_json,
        "status": task.status,
        "attempts": task.attempts,
        "max_attempts": task.max_attempts,
        "locked_at": task.locked_at,
        "completed_at": task.completed_at,
        "error_message": task.error_message,
        "idempotency_key": task.idempotency_key,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


@router.get("/org/agents")
def list_org_agents(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    agents = db.execute(select(OrgAgent).order_by(OrgAgent.id)).scalars().all()
    return [agent_payload(db, agent) for agent in agents]


@router.get("/org/agents/{agent_id}")
def get_org_agent(agent_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    agent = db.get(OrgAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Org agent not found")
    recent_activity = db.execute(
        select(ActivityEvent)
        .where(ActivityEvent.actor_id == agent.id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(20)
    ).scalars().all()
    recent_tasks = db.execute(select(Task).order_by(Task.created_at.desc()).limit(20)).scalars().all()
    return {
        **agent_payload(db, agent),
        "recent_activity": [activity_payload(event) for event in recent_activity],
        "recent_tasks": [task_payload(task) for task in recent_tasks],
    }


@router.patch("/org/agents/{agent_id}/status")
def set_agent_status(agent_id: int, payload: AgentStatusRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    allowed = {"disabled", "paused", "idle", "running", "waiting_human", "failed"}
    if payload.status not in allowed:
        raise HTTPException(status_code=422, detail="Invalid agent status")
    agent = db.get(OrgAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Org agent not found")
    if agent.name == "publisher_agent" and payload.status != "disabled":
        raise HTTPException(status_code=422, detail="Publisher Agent stays disabled until MAX step")
    agent.status = payload.status
    agent.last_heartbeat_at = datetime.now(UTC) if payload.status == "idle" else agent.last_heartbeat_at
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="agent_status_changed",
        entity_type="org_agent",
        entity_id=agent.id,
        message=f"{agent.title} status changed to {agent.status}.",
    )
    db.commit()
    return agent_payload(db, agent)


@router.post("/org/agents/{agent_id}/pause")
def pause_agent(agent_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return set_agent_status(agent_id, AgentStatusRequest(status="paused"), db)


@router.post("/org/agents/{agent_id}/resume")
def resume_agent(agent_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return set_agent_status(agent_id, AgentStatusRequest(status="idle"), db)


@router.get("/goals")
def list_goals(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    goals = db.execute(select(Goal).order_by(Goal.id)).scalars().all()
    return [goal_payload(goal) for goal in goals]


@router.get("/routines")
def list_routines(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    routines = db.execute(select(Routine).order_by(Routine.id)).scalars().all()
    return [routine_payload(routine) for routine in routines]


@router.patch("/routines/{routine_id}", response_model=None)
def update_routine(routine_id: int, payload: RoutineUpdateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(routine, key, value)
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="routine_updated",
        entity_type="routine",
        entity_id=routine.id,
        message=f"Routine updated: {routine.name}",
    )
    db.commit()
    return routine_payload(routine)


@router.post("/routines/{routine_id}/dry-run", response_model=None)
def dry_run_routine(routine_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    routine.last_run_status = "dry_run_ok"
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="routine_dry_run",
        entity_type="routine",
        entity_id=routine.id,
        message=f"Routine dry run: {routine.name}",
        metadata={"task_type": routine.task_type, "payload": routine.payload_json},
    )
    db.commit()
    return routine_payload(routine)


@router.post("/routines/{routine_id}/run-once", response_model=None)
def run_routine_once(routine_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    settings = get_settings(db)
    if not settings["global_routines_enabled"]:
        routine.last_run_status = "blocked_global_routines_disabled"
        log_activity(
            db,
            actor_type="system",
            actor_id=None,
            event_type="routine_blocked",
            entity_type="routine",
            entity_id=routine.id,
            message=f"Routine blocked because global routines switch is disabled: {routine.name}",
        )
        db.commit()
        return routine_payload(routine)
    routine.last_run_at = datetime.now(UTC)
    routine.last_run_status = "queued_placeholder"
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="routine_triggered",
        entity_type="routine",
        entity_id=routine.id,
        message=f"Routine manually triggered: {routine.name}",
        metadata={"idempotency_key": f"routine:{routine.id}:{datetime.now(UTC).date()}"},
    )
    db.commit()
    return routine_payload(routine)


@router.get("/activity")
def list_activity(
    event_type: str | None = Query(default=None),
    agent_id: int | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(ActivityEvent).order_by(ActivityEvent.created_at.desc()).limit(200)
    if event_type:
        stmt = stmt.where(ActivityEvent.event_type == event_type)
    if agent_id:
        stmt = stmt.where(ActivityEvent.actor_id == agent_id)
    if entity_type:
        stmt = stmt.where(ActivityEvent.entity_type == entity_type)
    events = db.execute(stmt).scalars().all()
    return [activity_payload(event) for event in events]


@router.get("/costs/summary")
def cost_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    start = today_start()
    settings = get_settings(db)
    rub_rate = float(settings.get("usd_to_rub_rate", 100))
    events = list(db.execute(select(CostEvent).where(CostEvent.created_at >= start)).scalars())
    agents = {agent.id: agent for agent in db.execute(select(OrgAgent)).scalars()}
    tasks = {task.id: task for task in db.execute(select(Task)).scalars()}
    channels = {channel.id: channel for channel in db.execute(select(Channel)).scalars()}

    total = round(sum(event.estimated_cost for event in events), 6)
    by_agent: dict[str, float] = {}
    by_task_type: dict[str, float] = {}
    by_channel: dict[str, float] = {}

    for event in events:
        agent_name = agents[event.agent_id].title if event.agent_id in agents else "Unassigned"
        by_agent[agent_name] = round(by_agent.get(agent_name, 0.0) + event.estimated_cost, 6)
        task = tasks.get(event.task_id) if event.task_id else None
        task_type = event.task_type or (task.task_type if task else "unknown")
        by_task_type[task_type] = round(by_task_type.get(task_type, 0.0) + event.estimated_cost, 6)
        channel_id = event.channel_id or (task.payload_json.get("channel_id") if task else None)
        channel_name = channels[channel_id].name if channel_id in channels else "Unassigned"
        by_channel[channel_name] = round(by_channel.get(channel_name, 0.0) + event.estimated_cost, 6)

    total_budget = float(settings["global_daily_budget_usd"])
    agent_summaries = [agent_payload(db, agent) for agent in agents.values()]
    warnings = [agent for agent in agent_summaries if agent["budget_warning"]]
    if total >= total_budget * 0.8:
        warnings.append({"title": "Global budget", "budget_warning": True, "daily_cost_used": total, "budget_daily": total_budget})
    return {
        "total_estimated_cost_today": total,
        "total_estimated_cost_today_rub": round(total * rub_rate, 2),
        "budget_daily_total": round(total_budget, 6),
        "budget_daily_total_rub": round(total_budget * rub_rate, 2),
        "budget_remaining": round(max(total_budget - total, 0.0), 6),
        "budget_remaining_rub": round(max(total_budget - total, 0.0) * rub_rate, 2),
        "rub_rate": rub_rate,
        "by_agent": by_agent,
        "by_channel": by_channel,
        "by_task_type": by_task_type,
        "budget_warnings": warnings,
    }
