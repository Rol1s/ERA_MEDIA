from datetime import UTC, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.all_models import AgentRun, Channel, Post, Task, Topic
from app.services.settings import daily_global_usage, get_settings

router = APIRouter()


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict[str, str | bool | int]:
    active_channels = db.scalar(select(func.count()).select_from(Channel).where(Channel.status == "active")) or 0
    system_settings = get_settings(db)
    return {
        "status": "ok",
        "service": "ERA Media Factory",
        "database_ok": True,
        "active_channels": active_channels,
        "dev_mode": settings.dev_mode,
        "system_mode": system_settings["system_mode"],
        "global_agents_enabled": system_settings["global_agents_enabled"],
        "global_routines_enabled": system_settings["global_routines_enabled"],
        "global_publishing_enabled": system_settings["global_publishing_enabled"],
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict[str, int | float]:
    today_start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    system_settings = get_settings(db)
    usage = daily_global_usage(db)
    return {
        "topics_found_today": db.scalar(select(func.count()).select_from(Topic).where(Topic.created_at >= today_start)) or 0,
        "posts_generated_today": db.scalar(select(func.count()).select_from(Post).where(Post.created_at >= today_start)) or 0,
        "mock_posts": db.scalar(select(func.count()).select_from(Post).where(Post.mock_only.is_(True))) or 0,
        "dry_run_posts": db.scalar(select(func.count()).select_from(Post).where(Post.generation_mode == "dry_run")) or 0,
        "live_posts": db.scalar(select(func.count()).select_from(Post).where(Post.generation_mode == "live")) or 0,
        "not_publishable_posts": db.scalar(select(func.count()).select_from(Post).where(Post.not_publishable_reason != "")) or 0,
        "posts_waiting_review": db.scalar(select(func.count()).select_from(Post).where(Post.status == "needs_review")) or 0,
        "scheduled_posts": db.scalar(select(func.count()).select_from(Post).where(Post.status == "scheduled")) or 0,
        "published_posts": db.scalar(select(func.count()).select_from(Post).where(Post.status == "published")) or 0,
        "failed_tasks": db.scalar(select(func.count()).select_from(Task).where(Task.status == "failed")) or 0,
        "estimated_cost_usage": db.scalar(select(func.coalesce(func.sum(AgentRun.estimated_cost), 0.0))) or 0.0,
        "real_llm_calls_today": db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.started_at >= today_start, AgentRun.provider != "mock")) or 0,
        "cost_today": float(usage["cost"]),
        "active_channels": db.scalar(select(func.count()).select_from(Channel).where(Channel.status == "active")) or 0,
        "global_daily_budget_usd": float(system_settings["global_daily_budget_usd"]),
        "budget_remaining": max(float(system_settings["global_daily_budget_usd"]) - float(usage["cost"]), 0.0),
        "daily_tokens_used": int(usage["tokens"]),
        "global_daily_token_limit": int(system_settings["global_daily_token_limit"]),
    }
