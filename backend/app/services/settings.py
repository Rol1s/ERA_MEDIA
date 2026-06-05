from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import CostEvent, SystemSetting

NON_BILLABLE_PROVIDERS = {"ollama", "mock", "zero_token", "deterministic", "local_ollama_optional"}

DEFAULT_SETTINGS: dict[str, Any] = {
    "system_mode": "mock",
    "runtime_mode": "",
    "real_newsroom_mode": True,
    "global_agents_enabled": False,
    "global_routines_enabled": False,
    "global_publishing_enabled": False,
    "cost_optimized": True,
    "global_daily_budget_usd": 1,
    "global_daily_token_limit": 100000,
    "auto_publish_enabled": False,
    "auto_publish_daily_limit": 5,
    "auto_publish_enabled_at": "",
    "auto_publish_timezone": "Europe/Moscow",
    "editorial_autopilot_enabled": False,
    "editorial_autopilot_batch_size": 2,
    "editorial_autopilot_max_risk_score": 45,
    "editorial_autopilot_min_quality_score": 82,
    "ft_live_enabled": False,
    "ft_live_max_posts_per_run": 3,
    "ft_live_items_per_source": 4,
    "ft_live_prompt_version": "ft-live-cheap-v1",
    "active_launch_channels": ["era-now", "era-food", "era-money"],
    "daily_briefing_enabled": False,
    "daily_briefing_time_msk": "07:00",
    "daily_briefing_timezone": "Europe/Moscow",
    "daily_package_enabled": True,
    "daily_package_post_times_msk": ["08:00", "09:30", "13:00", "16:00", "19:00"],
    "morning_agenda_max_llm_items": 50,
    "live_radar_scan_enabled": True,
    "live_radar_scan_scope": "launch",
    "live_radar_scan_max_sources": 30,
    "live_radar_scan_items_per_source": 5,
    "require_human_approval_for_all_posts": True,
    "ui_language": "ru",
    "usd_to_rub_rate": 100,
    "admin_notification_provider": "none",
    "admin_notification_target": "",
    "notify_on_review_needed": True,
    "notify_on_failure": True,
    "notify_on_budget_warning": True,
    "owner_bot_enabled": False,
    "owner_bot_allowed_chat_id": "",
    "owner_bot_webhook_secret": "",
    "owner_bot_update_offset": 0,
    "owner_bot_public_url": "",
    "submission_bot_url": "",
    "ai_brain_mode": "local_gemma",
    "ai_brain_provider": "ollama",
    "ai_brain_model": "gemma4:e4b",
    "ollama_base_url": "http://host.docker.internal:11434",
    "local_llm_queue_timeout": 180,
    "local_llm_request_timeout": 240,
    "local_llm_context_length": 8192,
    "local_brain_latency_limit_ms": 90000,
    "openai_blocked_in_local_mode": True,
    "mock_blocked_in_operator_path": True,
    "store_raw_llm_response": False,
}

MODE_ALIASES = {
    "mock": "MOCK",
    "dry_run": "DRY_RUN",
    "live": "LIVE_INTERNAL",
    "production_manual": "LIVE_INTERNAL",
    "production_auto": "AUTO_LIVE",
    "MOCK": "MOCK",
    "DRY_RUN": "DRY_RUN",
    "LIVE_INTERNAL": "LIVE_INTERNAL",
    "AUTO_LIVE": "AUTO_LIVE",
}
ALLOWED_RUNTIME_MODES = {"MOCK", "DRY_RUN", "LIVE_INTERNAL", "AUTO_LIVE"}


def normalized_runtime_mode(db: Session) -> str:
    explicit = get_setting(db, "runtime_mode")
    if explicit in ALLOWED_RUNTIME_MODES:
        return str(explicit)
    return MODE_ALIASES.get(str(get_setting(db, "system_mode")), "MOCK")


def auto_live_enabled(db: Session) -> bool:
    return (
        normalized_runtime_mode(db) == "AUTO_LIVE"
        and bool(get_setting(db, "auto_publish_enabled"))
        and bool(get_setting(db, "global_publishing_enabled"))
    )


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
    allowed_modes = {"mock", "dry_run", "live", "production_manual", "production_auto"}
    allowed_brain_modes = {"local_gemma", "openai"}
    allowed_languages = {"ru", "en"}
    for key, value in values.items():
        if key not in DEFAULT_SETTINGS:
            continue
        if key == "system_mode" and value not in allowed_modes:
            raise ValueError("Invalid system_mode")
        if key == "runtime_mode" and value not in {*ALLOWED_RUNTIME_MODES, ""}:
            raise ValueError("Invalid runtime_mode")
        if key == "ai_brain_mode" and value not in allowed_brain_modes:
            raise ValueError("Invalid ai_brain_mode")
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
        select(func.coalesce(func.sum(CostEvent.estimated_cost), 0.0)).where(
            CostEvent.created_at >= start,
            CostEvent.provider.not_in(NON_BILLABLE_PROVIDERS),
        )
    ) or 0.0
    tokens_input = db.scalar(
        select(func.coalesce(func.sum(CostEvent.tokens_input), 0)).where(
            CostEvent.created_at >= start,
            CostEvent.provider.not_in(NON_BILLABLE_PROVIDERS),
        )
    ) or 0
    tokens_output = db.scalar(
        select(func.coalesce(func.sum(CostEvent.tokens_output), 0)).where(
            CostEvent.created_at >= start,
            CostEvent.provider.not_in(NON_BILLABLE_PROVIDERS),
        )
    ) or 0
    return {"cost": float(cost), "tokens": int(tokens_input) + int(tokens_output)}


def ensure_global_budget(db: Session) -> None:
    settings = get_settings(db)
    if settings.get("ai_brain_mode") == "local_gemma":
        return
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
