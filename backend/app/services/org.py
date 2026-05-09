from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import ActivityEvent, CostEvent, OrgAgent, Task
from app.services.settings import ensure_global_budget

AGENT_NAME_MAP = {
    "research_agent": "world_scout_agent",
    "factcheck_agent": "factcheck_agent",
    "editor_agent": "editor_in_chief",
    "chief_editor_agent": "editor_in_chief",
    "review_queue": "distribution_director",
}


def today_start() -> datetime:
    return datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)


def find_org_agent(db: Session, runtime_agent_name: str) -> OrgAgent | None:
    org_name = AGENT_NAME_MAP.get(runtime_agent_name, runtime_agent_name)
    return db.execute(select(OrgAgent).where(OrgAgent.name == org_name)).scalar_one_or_none()


def log_activity(
    db: Session,
    *,
    actor_type: str,
    actor_id: int | None,
    event_type: str,
    entity_type: str,
    entity_id: int | None,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> ActivityEvent:
    event = ActivityEvent(
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event


def daily_agent_usage(db: Session, agent_id: int) -> dict[str, float | int]:
    start = today_start()
    cost = db.scalar(
        select(func.coalesce(func.sum(CostEvent.estimated_cost), 0.0)).where(
            CostEvent.agent_id == agent_id,
            CostEvent.created_at >= start,
        )
    ) or 0.0
    tokens_input = db.scalar(
        select(func.coalesce(func.sum(CostEvent.tokens_input), 0)).where(
            CostEvent.agent_id == agent_id,
            CostEvent.created_at >= start,
        )
    ) or 0
    tokens_output = db.scalar(
        select(func.coalesce(func.sum(CostEvent.tokens_output), 0)).where(
            CostEvent.agent_id == agent_id,
            CostEvent.created_at >= start,
        )
    ) or 0
    return {
        "cost": float(cost),
        "tokens": int(tokens_input) + int(tokens_output),
    }


def ensure_agent_budget(
    db: Session,
    agent: OrgAgent | None,
    *,
    manual_override: bool = False,
    enforce_spend_limit: bool = True,
) -> None:
    if agent is None:
        return
    if agent.status == "disabled":
        raise RuntimeError(f"{agent.title} is disabled")
    if agent.status not in {"idle", "running"} and not manual_override:
        raise RuntimeError(f"{agent.title} is {agent.status}")
    if not enforce_spend_limit:
        return
    ensure_global_budget(db)
    usage = daily_agent_usage(db, agent.id)
    budget_reached = agent.budget_daily > 0 and float(usage["cost"]) >= agent.budget_daily
    token_reached = agent.token_limit_daily > 0 and int(usage["tokens"]) >= agent.token_limit_daily
    if budget_reached or token_reached:
        agent.status = "paused"
        log_activity(
            db,
            actor_type="agent",
            actor_id=agent.id,
            event_type="budget_limit_reached",
            entity_type="org_agent",
            entity_id=agent.id,
            message=f"{agent.title} paused because daily budget or token limit was reached.",
            metadata={"usage": usage, "budget_daily": agent.budget_daily, "token_limit_daily": agent.token_limit_daily},
        )
        db.commit()
        raise RuntimeError(f"{agent.title} reached daily budget or token limit")


def create_cost_event_for_run(
    db: Session,
    *,
    agent: OrgAgent | None,
    task_id: int | None,
    channel_id: int | None,
    task_type: str,
    provider: str,
    model: str,
    tokens_input: int,
    tokens_output: int,
    estimated_cost: float,
) -> CostEvent | None:
    if tokens_input == 0 and tokens_output == 0 and estimated_cost == 0:
        return None
    event = CostEvent(
        agent_id=agent.id if agent else None,
        task_id=task_id,
        channel_id=channel_id,
        task_type=task_type,
        provider=provider,
        model=model,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        estimated_cost=estimated_cost,
    )
    db.add(event)
    return event


def task_relation(task: Task | None) -> dict[str, Any]:
    if task is None:
        return {}
    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "topic_id": task.payload_json.get("topic_id"),
        "post_id": task.payload_json.get("post_id"),
        "channel_id": task.payload_json.get("channel_id"),
    }
