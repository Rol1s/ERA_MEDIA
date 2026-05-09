from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import CostEvent, SystemSetting

DEFAULT_SETTINGS: dict[str, Any] = {
    "system_mode": "mock",
    "global_agents_enabled": False,
    "global_routines_enabled": False,
    "global_publishing_enabled": False,
    "global_daily_budget_usd": 2,
    "global_daily_token_limit": 100000,
    "require_human_approval_for_all_posts": True,
    "ui_language": "ru",
    "usd_to_rub_rate": 100,
    "admin_notification_provider": "none",
    "admin_notification_target": "",
    "notify_on_review_needed": True,
    "notify_on_failure": True,
    "notify_on_budget_warning": True,
}


def today_start() -> datetime:
    return datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)


def get_setting(db: Session, key: str) -> Any:
    setting = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if setting is None:
        value = DEFAULT_SETTINGS[key]
        db.add(SystemSetting(key=key, value_json={"value": value}))
        db.flush()
        return value
    return setting.value_json.get("value")


def get_settings(db: Session) -> dict[str, Any]:
    return {key: get_setting(db, key) for key in DEFAULT_SETTINGS}


def update_settings(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    allowed_modes = {"mock", "dry_run", "live"}
    allowed_languages = {"ru", "en"}
    for key, value in values.items():
        if key not in DEFAULT_SETTINGS:
            continue
        if key == "system_mode" and value not in allowed_modes:
            raise ValueError("Invalid system_mode")
        if key == "ui_language" and value not in allowed_languages:
            raise ValueError("Invalid ui_language")
        setting = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
        if setting is None:
            setting = SystemSetting(key=key)
            db.add(setting)
        setting.value_json = {"value": value}
    db.commit()
    return get_settings(db)


def daily_global_usage(db: Session) -> dict[str, float | int]:
    start = today_start()
    cost = db.scalar(
        select(func.coalesce(func.sum(CostEvent.estimated_cost), 0.0)).where(CostEvent.created_at >= start)
    ) or 0.0
    tokens_input = db.scalar(
        select(func.coalesce(func.sum(CostEvent.tokens_input), 0)).where(CostEvent.created_at >= start)
    ) or 0
    tokens_output = db.scalar(
        select(func.coalesce(func.sum(CostEvent.tokens_output), 0)).where(CostEvent.created_at >= start)
    ) or 0
    return {"cost": float(cost), "tokens": int(tokens_input) + int(tokens_output)}


def ensure_global_budget(db: Session) -> None:
    settings = get_settings(db)
    usage = daily_global_usage(db)
    if float(usage["cost"]) >= float(settings["global_daily_budget_usd"]):
        raise RuntimeError("Global daily budget exceeded")
    if int(usage["tokens"]) >= int(settings["global_daily_token_limit"]):
        raise RuntimeError("Global daily token limit exceeded")


def ensure_global_agents_enabled(db: Session, *, manual_override: bool = False) -> None:
    if manual_override:
        return
    if not bool(get_setting(db, "global_agents_enabled")):
        raise RuntimeError("Global agents switch is disabled")


def ensure_global_routines_enabled(db: Session) -> None:
    if not bool(get_setting(db, "global_routines_enabled")):
        raise RuntimeError("Global routines switch is disabled")
