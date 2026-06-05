import os
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.db.session import SessionLocal, get_db
from app.models.all_models import (
    ActivityEvent,
    AgentConfig,
    AgentRun,
    Channel,
    CostEvent,
    DecisionLog,
    Integration,
    Issue,
    LLMModel,
    Notification,
    OperatingLoopRun,
    OrgAgent,
    PlatformChannel,
    Post,
    PromptTemplate,
    Topic,
)
from app.agents.llm_provider import LLMConfigurationError, provider_for_name
from app.services.brain_mode import assert_provider_allowed
from app.services.agent_role_files import apply_agent_role_files, role_file_preview
from app.services.kanban import ISSUE_TRANSITIONS, KanbanStateMachine, allowed_transitions, issue_tree_progress
from app.services.llm_config import resolve_prompt_template
from app.services.notifications import create_notification, dispatch_notification
from app.services.org import daily_agent_usage, log_activity
from app.services.secrets import PROVIDER_SECRET_NAMES, get_secret_row, resolve_secret_value
from app.services.settings import get_settings

router = APIRouter()
MAX_DEFAULT_BASE_URL = "https://platform-api.max.ru"
PROVIDER_ENV = {**PROVIDER_SECRET_NAMES, "ollama": "OLLAMA_BASE_URL", "local_ollama_optional": "OLLAMA_BASE_URL", "mock": ""}


def provider_readiness(db: Session, config: AgentConfig | None) -> dict[str, Any]:
    if config is None:
        return {"ready_for_mock": False, "ready_for_dry_run": False, "reason": "Agent config is missing"}
    env_name = PROVIDER_ENV.get(config.provider, "")
    stored = get_secret_row(db, config.provider, env_name) if config.provider in PROVIDER_SECRET_NAMES else None
    key_present = bool(stored and stored.status in {"configured", "verified"}) or bool(os.getenv(env_name))
    env_present = True if config.provider == "mock" else key_present
    model_enabled = bool(config.model)
    ready_for_mock = config.provider == "mock"
    ready_for_dry_run = config.enabled and config.provider != "mock" and env_present and model_enabled
    reasons = []
    if not config.enabled:
        reasons.append("config disabled")
    if config.provider == "mock":
        reasons.append("provider=mock")
    if config.provider != "mock" and not env_present:
        reasons.append(f"Missing environment variable: {env_name}")
    if not model_enabled:
        reasons.append("model is empty")
    return {
        "ready_for_mock": ready_for_mock,
        "ready_for_dry_run": ready_for_dry_run,
        "provider": config.provider,
        "model": config.model,
        "required_env": env_name,
        "env_key_present": env_present,
        "stored_key_present": bool(stored and stored.status in {"configured", "verified"}),
        "structured_output": config.provider in {"mock", "openai", "anthropic", "gemini", "ollama", "local_ollama_optional"},
        "budget_available": config.daily_budget_usd != 0,
        "reason": "; ".join(reasons) if reasons else "ready",
    }


def _max_get_me(base_url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/me",
        headers={"Authorization": token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return {"ok": True, "status": response.status, "body": response.read().decode("utf-8", errors="replace")[:600]}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "body": exc.read().decode("utf-8", errors="replace")[:600]}


def _max_get_chat(base_url: str, token: str, chat_id: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chats/{chat_id}",
        headers={"Authorization": token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return {"ok": True, "status": response.status, "body": response.read().decode("utf-8", errors="replace")[:1200]}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "body": exc.read().decode("utf-8", errors="replace")[:1200]}


def _max_get_chats(base_url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chats?count=100",
        headers={"Authorization": token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return {"ok": True, "status": response.status, "body": response.read().decode("utf-8", errors="replace")[:12000]}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "body": exc.read().decode("utf-8", errors="replace")[:12000]}


class IntegrationUpdate(BaseModel):
    status: str | None = None
    config_json: dict[str, Any] | None = None
    secret_ref: str | None = None


class PlatformChannelUpdate(BaseModel):
    external_chat_id: str | None = None
    external_channel_url: str | None = None
    integration_id: int | None = None
    status: str | None = None
    publish_mode: str | None = None
    can_publish: bool | None = None


class MaxChannelStartRequest(BaseModel):
    chat_id: str
    title: str | None = None
    link: str | None = None


class IssueUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    result_summary: str | None = None
    owner_agent_id: int | None = None
    reviewer_agent_id: int | None = None
    blocked_by_issue_id: int | None = None
    next_action: str | None = None
    blocked_reason: str | None = None
    required_human_action: str | None = None
    target_metric: str | None = None
    target_value: float | None = None
    current_value: float | None = None
    progress_json: dict[str, Any] | None = None


class SubIssueCreate(BaseModel):
    title: str
    description: str = ""
    issue_type: str = "maintenance"
    owner_agent_id: int | None = None
    reviewer_agent_id: int | None = None
    priority: str = "normal"


class AgentConfigUpdate(BaseModel):
    prompt_template_id: int | None = None
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    system_prompt: str | None = None
    tools_json: list[dict[str, Any]] | None = None
    daily_budget_usd: float | None = None
    daily_token_limit: int | None = None
    max_runs_per_day: int | None = None
    timeout_seconds: int | None = None
    enabled: bool | None = None


class BulkOpenAIContentAgentsRequest(BaseModel):
    model: str | None = None


class ApplyAgentRoleFilesRequest(BaseModel):
    confirm: bool = False


class PromptTemplateCreate(BaseModel):
    name: str
    agent_type: str
    content: str
    variables_json: dict[str, Any] = {}
    status: str = "draft"


class PromptTemplateUpdate(BaseModel):
    content: str | None = None
    variables_json: dict[str, Any] | None = None
    status: str | None = None


def integration_payload(item: Integration) -> dict[str, Any]:
    config = dict(item.config_json or {})
    if "token" in config:
        config["token"] = "***"
    return {
        "id": item.id,
        "name": item.name,
        "provider": item.provider,
        "type": item.type,
        "status": item.status,
        "config_json": config,
        "secret_ref": item.secret_ref,
        "secret_configured": bool(item.secret_ref and os.getenv(item.secret_ref)),
        "required_env_template": f"{item.secret_ref}=..." if item.secret_ref else "",
        "last_check_at": item.last_check_at,
        "last_success_at": item.last_success_at,
        "last_error": item.last_error,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def platform_payload(item: PlatformChannel) -> dict[str, Any]:
    return {
        "id": item.id,
        "channel_id": item.channel_id,
        "platform": item.platform,
        "external_chat_id": item.external_chat_id,
        "external_channel_url": item.external_channel_url,
        "integration_id": item.integration_id,
        "status": item.status,
        "publish_mode": item.publish_mode,
        "can_publish": item.can_publish,
        "last_test_at": item.last_test_at,
        "last_success_at": item.last_success_at,
        "last_error": item.last_error,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def channel_payload(item: Channel) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "platform": item.platform,
        "category": item.category,
        "description": item.description,
        "tone_of_voice": item.tone_of_voice,
        "audience_description": item.audience_description,
        "topics_allowed": item.topics_allowed,
        "topics_forbidden": item.topics_forbidden,
        "posting_frequency_per_day": item.posting_frequency_per_day,
        "daily_post_limit": item.daily_post_limit,
        "publish_mode": item.publish_mode,
        "auto_publish_enabled": item.auto_publish_enabled,
        "risk_threshold": item.risk_threshold,
        "channel_mode": item.channel_mode,
        "relay_mode": item.relay_mode,
        "relay_source_ids": item.relay_source_ids,
        "relay_publish_delay_minutes": item.relay_publish_delay_minutes,
        "relay_max_posts_per_day": item.relay_max_posts_per_day,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _slugify_channel_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "max-channel"


def _unique_channel_slug(db: Session, base: str, *, existing_channel_id: int | None = None) -> str:
    slug = base
    index = 2
    while True:
        existing = db.execute(select(Channel).where(Channel.slug == slug)).scalar_one_or_none()
        if existing is None or existing.id == existing_channel_id:
            return slug
        slug = f"{base}-{index}"
        index += 1


def notification_payload(item: Notification) -> dict[str, Any]:
    return {
        "id": item.id,
        "severity": item.severity,
        "title": item.title,
        "message": item.message,
        "entity_type": item.entity_type,
        "entity_id": item.entity_id,
        "status": item.status,
        "created_at": item.created_at,
        "read_at": item.read_at,
    }


def issue_payload(item: Issue) -> dict[str, Any]:
    return {
        "id": item.id,
        "parent_issue_id": item.parent_issue_id,
        "root_issue_id": item.root_issue_id,
        "delegation_level": item.delegation_level,
        "blocked_by_issue_id": item.blocked_by_issue_id,
        "title": item.title,
        "description": item.description,
        "issue_type": item.issue_type,
        "owner_agent_id": item.owner_agent_id,
        "reviewer_agent_id": item.reviewer_agent_id,
        "related_channel_id": item.related_channel_id,
        "related_topic_id": item.related_topic_id,
        "related_post_id": item.related_post_id,
        "priority": item.priority,
        "status": item.status,
        "next_action": item.next_action,
        "blocked_reason": item.blocked_reason,
        "required_human_action": item.required_human_action,
        "target_metric": item.target_metric,
        "target_value": item.target_value,
        "current_value": item.current_value,
        "progress_json": item.progress_json,
        "idempotency_key": item.idempotency_key,
        "sub_issue_count": int((item.progress_json or {}).get("sub_issues_total", 0)),
        "result_summary": item.result_summary,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "completed_at": item.completed_at,
    }


def agent_config_payload(item: AgentConfig) -> dict[str, Any]:
    return {
        "id": item.id,
        "org_agent_id": item.org_agent_id,
        "prompt_template_id": item.prompt_template_id,
        "provider": item.provider,
        "model": item.model,
        "temperature": item.temperature,
        "max_tokens": item.max_tokens,
        "system_prompt": item.system_prompt,
        "tools_json": item.tools_json,
        "daily_budget_usd": item.daily_budget_usd,
        "daily_token_limit": item.daily_token_limit,
        "max_runs_per_day": item.max_runs_per_day,
        "timeout_seconds": item.timeout_seconds,
        "enabled": item.enabled,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def llm_model_payload(item: LLMModel) -> dict[str, Any]:
    return {
        "id": item.id,
        "provider": item.provider,
        "model": item.model,
        "label": item.label,
        "input_cost_per_1m": item.input_cost_per_1m,
        "output_cost_per_1m": item.output_cost_per_1m,
        "supports_tools": item.supports_tools,
        "supports_json_schema": item.supports_json_schema,
        "enabled": item.enabled,
    }


def prompt_payload(item: PromptTemplate) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "agent_type": item.agent_type,
        "version": item.version,
        "content": item.content,
        "variables_json": item.variables_json,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def decision_payload(item: DecisionLog) -> dict[str, Any]:
    return {
        "id": item.id,
        "agent_run_id": item.agent_run_id,
        "issue_id": item.issue_id,
        "entity_type": item.entity_type,
        "entity_id": item.entity_id,
        "decision": item.decision,
        "reason": item.reason,
        "confidence": item.confidence,
        "alternatives_json": item.alternatives_json,
        "created_at": item.created_at,
    }


@router.get("/integrations", response_model=None)
def list_integrations(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    items = db.execute(select(Integration).order_by(Integration.id)).scalars().all()
    return [integration_payload(item) for item in items]


@router.patch("/integrations/{integration_id}", response_model=None)
def update_integration(integration_id: int, payload: IntegrationUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Integration, integration_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="integration_updated",
        entity_type="integration",
        entity_id=item.id,
        message=f"Integration updated: {item.name}",
    )
    db.commit()
    return integration_payload(item)


@router.post("/integrations/{integration_id}/test", response_model=None)
def test_integration(integration_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Integration, integration_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    item.last_check_at = datetime.now(UTC)
    settings = get_settings(db)
    ok = True
    error = ""
    test_result: dict[str, Any] = {}
    if item.provider == "max":
        config = dict(item.config_json or {})
        base_url = config.get("MAX_API_BASE_URL") or config.get("api_base_url") or MAX_DEFAULT_BASE_URL
        try:
            token = resolve_secret_value(db, "max", item.secret_ref or "MAX_BOT_TOKEN")
        except Exception:
            token = os.getenv(item.secret_ref or "MAX_BOT_TOKEN")
        dry_run_payload = {"method": "POST", "url": f"{base_url.rstrip('/')}/messages", "headers": {"Authorization": "***"}, "body": {"chat_id": config.get("default_admin_chat_id"), "text": "ERA dry-run admin test"}}
        test_result = {
            "base_url": base_url,
            "expected_base_url": MAX_DEFAULT_BASE_URL,
            "token_status": "found" if token else "missing",
            "dry_run_message_payload": dry_run_payload,
        }
        if base_url != MAX_DEFAULT_BASE_URL and not config.get("allow_custom_base_url"):
            ok = False
            error = "MAX_API_BASE_URL must be https://platform-api.max.ru unless allow_custom_base_url=true"
        elif not item.secret_ref or not token:
            ok = False
            error = f"Bot token env {item.secret_ref or '(empty)'} is not configured"
        else:
            me_result = _max_get_me(base_url, token)
            test_result["me"] = me_result
            ok = bool(me_result["ok"])
            if not ok:
                error = f"MAX /me check failed: HTTP {me_result.get('status')}"
    elif item.type == "llm" and settings["system_mode"] == "mock":
        provider_name = item.provider if item.provider in {"openai", "anthropic", "gemini", "local_ollama_optional"} else "mock"
        env_name = item.secret_ref or PROVIDER_ENV[provider_name]
        ok = provider_name == "mock" or bool(os.getenv(env_name))
        error = "" if ok else f"Missing environment variable: {env_name}"
        test_result = {"mode": "mock", "external_call": False, "provider": provider_name, "required_env": env_name, "env_status": "found" if ok else "missing"}
    elif item.type == "llm":
        provider_name = item.provider
        model = (item.config_json or {}).get("model") or ("gpt-4.1-mini" if provider_name == "openai" else "mock")
        try:
            api_key = None
            if provider_name in PROVIDER_SECRET_NAMES:
                api_key = resolve_secret_value(db, provider_name, PROVIDER_SECRET_NAMES[provider_name])
            provider = provider_for_name(provider_name, model=model, api_key=api_key)
            response = provider.generate_structured(
                system_prompt="Return a tiny JSON health check.",
                user_prompt="Say ok for ERA Media Factory provider test.",
                output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False},
                model=model,
                temperature=0,
                max_tokens=64,
                timeout_seconds=15,
            )
            test_result = {"provider": response.provider, "model": response.model, "usage": response.usage.__dict__}
            db.add(
                CostEvent(
                    task_type="integration_provider_test",
                    provider=response.provider,
                    model=response.model,
                    tokens_input=response.usage.tokens_input,
                    tokens_output=response.usage.tokens_output,
                    estimated_cost=response.usage.estimated_cost,
                )
            )
        except LLMConfigurationError as exc:
            ok = False
            error = str(exc)
        except Exception as exc:
            ok = False
            error = str(exc)
    elif item.status == "disabled":
        ok = False
        error = "Integration is disabled"

    if ok:
        item.status = "configured" if item.status == "not_configured" else item.status
        item.last_success_at = datetime.now(UTC)
        item.last_error = ""
        event_type = "integration_test_success"
        message = f"Integration test success: {item.name}"
    else:
        item.status = "failed"
        item.last_error = error
        event_type = "integration_test_failed"
        message = f"Integration test failed: {item.name}: {error}"
        create_notification(
            db,
            severity="warning",
            title="Интеграция не прошла проверку",
            message=message,
            entity_type="integration",
            entity_id=item.id,
        )
    log_activity(db, actor_type="system", actor_id=None, event_type=event_type, entity_type="integration", entity_id=item.id, message=message)
    db.commit()
    config = dict(item.config_json or {})
    if item.provider == "max":
        config["last_test_result"] = test_result
        config["MAX_API_BASE_URL"] = config.get("MAX_API_BASE_URL") or MAX_DEFAULT_BASE_URL
        item.config_json = config
        db.commit()
    return {"ok": ok, "error": error, "result": test_result, "integration": integration_payload(item)}


@router.post("/integrations/{integration_id}/test-admin-message", response_model=None)
def test_admin_message(integration_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Integration, integration_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    notification = create_notification(
        db,
        severity="info",
        title="Тест админ-уведомления",
        message=f"Dry-run notification through {item.name}. Public publishing is disabled.",
        entity_type="integration",
        entity_id=item.id,
    )
    result = dispatch_notification(db, notification)
    db.commit()
    return {"ok": True, "dispatch": result}


@router.get("/platform-channels", response_model=None)
def list_platform_channels(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    max_integration = db.execute(select(Integration).where(Integration.provider == "max")).scalar_one_or_none()
    channels = db.execute(select(Channel).order_by(Channel.id)).scalars().all()
    for channel in channels:
        existing = db.execute(
            select(PlatformChannel).where(
                PlatformChannel.channel_id == channel.id,
                PlatformChannel.platform == "max",
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                PlatformChannel(
                    channel_id=channel.id,
                    platform="max",
                    integration_id=max_integration.id if max_integration else None,
                    publish_mode="manual_copy",
                    can_publish=False,
                    status="not_connected",
                )
            )
    db.commit()
    items = db.execute(select(PlatformChannel).order_by(PlatformChannel.channel_id)).scalars().all()
    return [platform_payload(item) for item in items]


@router.get("/platform-channels/max/discover", response_model=None)
def discover_max_chats(db: Session = Depends(get_db)) -> dict[str, Any]:
    integration = db.execute(select(Integration).where(Integration.provider == "max")).scalar_one_or_none()
    base_url = ((integration.config_json or {}).get("MAX_API_BASE_URL") if integration else None) or MAX_DEFAULT_BASE_URL
    token = ""
    if integration:
        try:
            token = resolve_secret_value(db, "max", integration.secret_ref or "MAX_BOT_TOKEN")
        except Exception:
            token = os.getenv(integration.secret_ref or "MAX_BOT_TOKEN") or ""
    if not token:
        raise HTTPException(status_code=422, detail="MAX bot token is missing. Add MAX_BOT_TOKEN first.")
    result = _max_get_chats(base_url, token)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"MAX chats discovery failed: HTTP {result.get('status')} {result.get('body', '')[:300]}")
    try:
        import json

        body = json.loads(result.get("body") or "{}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MAX returned invalid JSON: {exc}") from exc
    chats = body.get("chats") or body.get("items") or []
    safe_chats = [
        {
            "chat_id": item.get("chat_id"),
            "type": item.get("type"),
            "status": item.get("status"),
            "title": item.get("title"),
            "link": item.get("link"),
            "is_public": item.get("is_public"),
            "participants_count": item.get("participants_count"),
        }
        for item in chats
        if isinstance(item, dict)
    ]
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="max_chats_discovered",
        entity_type="integration",
        entity_id=integration.id if integration else None,
        message=f"MAX chats discovery returned {len(safe_chats)} chats. No publishing was called.",
        metadata={"count": len(safe_chats), "publishing_enabled": False},
    )
    db.commit()
    return {"ok": True, "chats": safe_chats, "marker": body.get("marker"), "max_called": False, "published": False}


@router.post("/platform-channels/max/start", response_model=None)
def start_max_channel(payload: MaxChannelStartRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    chat_id = str(payload.chat_id or "").strip()
    if not chat_id:
        raise HTTPException(status_code=422, detail="MAX chat_id is required")

    integration = db.execute(select(Integration).where(Integration.provider == "max")).scalar_one_or_none()
    platform = db.execute(
        select(PlatformChannel).where(
            PlatformChannel.platform == "max",
            PlatformChannel.external_chat_id == chat_id,
        )
    ).scalar_one_or_none()

    if platform:
        channel = db.get(Channel, platform.channel_id)
        if channel is None:
            channel = Channel(
                name=(payload.title or f"MAX {chat_id}").strip()[:120],
                slug=_unique_channel_slug(db, _slugify_channel_name(payload.title or f"max-{chat_id}")),
                platform="max",
                category="news",
                description="",
                channel_mode="newsroom",
                publish_mode="manual",
                auto_publish_enabled=False,
                status="active",
            )
            db.add(channel)
            db.flush()
            platform.channel_id = channel.id
    else:
        title = (payload.title or f"MAX {chat_id}").strip()[:120]
        base_slug = _slugify_channel_name(payload.title or f"max-{chat_id}")
        channel = Channel(
            name=title,
            slug=_unique_channel_slug(db, base_slug),
            platform="max",
            category="news",
            description="",
            channel_mode="newsroom",
            publish_mode="manual",
            auto_publish_enabled=False,
            status="active",
        )
        db.add(channel)
        db.flush()
        platform = PlatformChannel(
            channel_id=channel.id,
            platform="max",
            external_chat_id=chat_id,
            external_channel_url=(payload.link or "").strip(),
            integration_id=integration.id if integration else None,
            status="not_connected",
            publish_mode="manual_copy",
            can_publish=False,
        )
        db.add(platform)
        db.flush()

    channel.status = "active"
    channel.platform = "max"
    channel.channel_mode = "newsroom"
    channel.publish_mode = "manual"
    channel.auto_publish_enabled = False
    platform.external_chat_id = chat_id
    if payload.link:
        platform.external_channel_url = payload.link.strip()
    if integration and not platform.integration_id:
        platform.integration_id = integration.id
    if platform.publish_mode == "auto_publish":
        platform.publish_mode = "manual_copy"
        platform.can_publish = False

    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="max_channel_started",
        entity_type="channel",
        entity_id=channel.id,
        message=f"MAX channel workspace started for {channel.name}. No publishing or agents were called.",
        metadata={"chat_id": chat_id, "platform_channel_id": platform.id, "max_called": False, "llm_called": False, "publishing_called": False},
    )
    db.commit()
    db.refresh(channel)
    db.refresh(platform)
    return {"ok": True, "channel": channel_payload(channel), "platform_channel": platform_payload(platform), "max_called": False, "published": False}


@router.patch("/platform-channels/{platform_channel_id}", response_model=None)
def update_platform_channel(platform_channel_id: int, payload: PlatformChannelUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(PlatformChannel, platform_channel_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Platform channel not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    if item.publish_mode == "auto_publish":
        item.can_publish = False
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="platform_channel_updated",
        entity_type="platform_channel",
        entity_id=item.id,
        message=f"Platform channel updated: channel #{item.channel_id}",
    )
    db.commit()
    return platform_payload(item)


@router.post("/platform-channels/{platform_channel_id}/test", response_model=None)
def test_platform_channel(platform_channel_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(PlatformChannel, platform_channel_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Platform channel not found")
    item.last_test_at = datetime.now(UTC)
    integration = db.get(Integration, item.integration_id) if item.integration_id else db.execute(select(Integration).where(Integration.provider == "max")).scalar_one_or_none()
    base_url = ((integration.config_json or {}).get("MAX_API_BASE_URL") if integration else None) or MAX_DEFAULT_BASE_URL
    token = ""
    if integration:
        try:
            token = resolve_secret_value(db, "max", integration.secret_ref or "MAX_BOT_TOKEN")
        except Exception:
            token = os.getenv(integration.secret_ref or "MAX_BOT_TOKEN") or ""
    result: dict[str, Any] = {"external_call": False, "base_url": base_url}
    if not token:
        item.status = "failed"
        item.last_error = "MAX bot token is missing. Add MAX_BOT_TOKEN in Integrations first."
        ok = False
    elif not item.external_chat_id:
        item.status = "failed"
        item.last_error = "MAX chat_id/channel_id is empty"
        ok = False
    else:
        result = _max_get_chat(base_url, token, item.external_chat_id.strip())
        result["external_call"] = True
        ok = bool(result.get("ok"))
        if ok:
            item.status = "connected"
            item.last_success_at = datetime.now(UTC)
            item.last_error = ""
            item.can_publish = True
            item.publish_mode = "semi_auto_approval" if item.publish_mode in {"manual_copy", "auto_publish"} else item.publish_mode
        else:
            item.status = "failed"
            item.last_error = f"MAX chat check failed: HTTP {result.get('status')} {result.get('body', '')[:300]}"
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="platform_channel_test_success" if ok else "platform_channel_test_failed",
        entity_type="platform_channel",
        entity_id=item.id,
        message=f"Platform channel test {'success' if ok else 'failed'} for channel #{item.channel_id}",
        metadata={"max_result": result, "publishing_enabled": bool(ok)},
    )
    if not ok:
        create_notification(
            db,
            severity="warning",
            title="MAX канал не прошел проверку",
            message=item.last_error,
            entity_type="platform_channel",
            entity_id=item.id,
        )
    db.commit()
    return {"ok": ok, "result": result, "platform_channel": platform_payload(item)}


@router.get("/notifications", response_model=None)
def list_notifications(status: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    stmt = select(Notification).order_by(Notification.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(Notification.status == status)
    else:
        stmt = stmt.where(Notification.status != "archived")
    items = db.execute(stmt).scalars().all()
    return [notification_payload(item) for item in items]


@router.get("/notifications/unread-count")
def unread_notifications(db: Session = Depends(get_db)) -> dict[str, int]:
    count = db.scalar(select(func.count()).select_from(Notification).where(Notification.status == "unread")) or 0
    return {"unread": int(count)}


@router.post("/notifications/{notification_id}/read", response_model=None)
def mark_notification_read(notification_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Notification, notification_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    item.status = "read"
    item.read_at = datetime.now(UTC)
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="notification_read",
        entity_type="notification",
        entity_id=item.id,
        message=f"Notification marked as read: {item.title}",
    )
    db.commit()
    return notification_payload(item)


@router.post("/notifications/archive-all", response_model=None)
def archive_all_notifications(db: Session = Depends(get_db)) -> dict[str, int]:
    items = db.execute(select(Notification).where(Notification.status != "archived")).scalars().all()
    now = datetime.now(UTC)
    for item in items:
        item.status = "archived"
        if item.read_at is None:
            item.read_at = now
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="notifications_archived",
        entity_type="notification",
        entity_id=None,
        message=f"Archived {len(items)} notifications from operator workspace.",
    )
    db.commit()
    return {"archived": len(items)}


@router.get("/issues", response_model=None)
def list_issues(show_closed: bool = Query(False), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    stmt = (
        select(Issue)
        .where(Issue.issue_type != "smoke", ~Issue.title.ilike("Smoke %"))
        .order_by(Issue.created_at.desc())
        .limit(200)
    )
    if not show_closed:
        stmt = stmt.where(Issue.status.notin_(["completed", "failed", "cancelled"]))
    items = db.execute(
        stmt
    ).scalars().all()
    return [issue_payload(item) for item in items]


@router.patch("/issues/{issue_id}", response_model=None)
def update_issue(issue_id: int, payload: IssueUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Issue, issue_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] != item.status:
        target = data["status"]
        try:
            KanbanStateMachine(db).transition(
                item,
                target,
                actor_type="human",
                actor_id=None,
                reason="Manual Kanban transition from UI/API.",
                create_decision=True,
            )
        except ValueError as exc:
            db.commit()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        data.pop("status")
    for key, value in data.items():
        setattr(item, key, value)
    if item.status in {"completed", "failed", "cancelled"} and item.completed_at is None:
        item.completed_at = datetime.now(UTC)
    item.progress_json = {**(item.progress_json or {}), **issue_tree_progress(db, item)}
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="issue_updated",
        entity_type="issue",
        entity_id=item.id,
        message=f"Issue updated: {item.title}",
    )
    db.commit()
    return issue_payload(item)


@router.get("/issues/{issue_id}/detail", response_model=None)
def issue_detail(issue_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Issue, issue_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    parent = db.get(Issue, item.parent_issue_id) if item.parent_issue_id else None
    children = db.execute(select(Issue).where(Issue.parent_issue_id == item.id).order_by(Issue.created_at)).scalars().all()
    decisions = db.execute(select(DecisionLog).where(DecisionLog.issue_id == item.id).order_by(DecisionLog.created_at.desc()).limit(50)).scalars().all()
    activity = db.execute(
        select(ActivityEvent).where(ActivityEvent.entity_type == "issue", ActivityEvent.entity_id == item.id).order_by(ActivityEvent.created_at.desc()).limit(50)
    ).scalars().all()
    return {
        "issue": issue_payload(item),
        "parent": issue_payload(parent) if parent else None,
        "sub_issues": [issue_payload(child) for child in children],
        "allowed_transitions": allowed_transitions(item.status),
        "progress": issue_tree_progress(db, item),
        "decision_logs": [decision_payload(decision) for decision in decisions],
        "activity": [
            {
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
            for event in activity
        ],
    }


@router.post("/issues/{issue_id}/sub-issues", response_model=None)
def create_sub_issue(issue_id: int, payload: SubIssueCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    parent = db.get(Issue, issue_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent issue not found")
    ceo = db.execute(select(OrgAgent).where(OrgAgent.name == "human_owner")).scalar_one_or_none()
    expansion_text = f"{payload.title} {payload.description} {payload.issue_type}".lower()
    needs_ceo = any(
        token in expansion_text
        for token in ["org", "organization", "структур", "агент", "agent", "director", "role", "роль", "расшир"]
    )
    item = Issue(
        title=payload.title,
        description=payload.description,
        issue_type=payload.issue_type,
        owner_agent_id=payload.owner_agent_id,
        reviewer_agent_id=ceo.id if needs_ceo and ceo else payload.reviewer_agent_id or parent.reviewer_agent_id,
        related_channel_id=parent.related_channel_id,
        related_topic_id=parent.related_topic_id,
        related_post_id=parent.related_post_id,
        priority=payload.priority,
        status="waiting_human" if needs_ceo else "backlog",
        parent_issue_id=parent.id,
        root_issue_id=parent.root_issue_id or parent.id,
        delegation_level=parent.delegation_level + 1,
        next_action="CEO/Human Owner must approve org-structure expansion before work starts." if needs_ceo else "Owner should move this issue to ready when scope is clear.",
        required_human_action="Approve, reject or simplify this org-structure expansion." if needs_ceo else "",
        progress_json={"manual_delegation": True, "ceo_approval_required": needs_ceo},
    )
    db.add(item)
    db.flush()
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="issue_delegated",
        entity_type="issue",
        entity_id=item.id,
        message=f"Sub-issue created under #{parent.id}: {item.title}",
        metadata={"parent_issue_id": parent.id, "root_issue_id": item.root_issue_id},
    )
    db.commit()
    return issue_payload(item)


@router.get("/decision-logs", response_model=None)
def list_decisions(
    entity_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None),
    issue_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(DecisionLog).order_by(DecisionLog.created_at.desc()).limit(200)
    if entity_type:
        stmt = stmt.where(DecisionLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(DecisionLog.entity_id == entity_id)
    if issue_id:
        stmt = stmt.where(DecisionLog.issue_id == issue_id)
    items = db.execute(stmt).scalars().all()
    return [decision_payload(item) for item in items]


@router.get("/agents/telemetry", response_model=None)
def agents_telemetry(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    agents = db.execute(select(OrgAgent).order_by(OrgAgent.id)).scalars().all()
    today = datetime.now(UTC).date()
    start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    rows: list[dict[str, Any]] = []
    for agent in agents:
        runtime_names = [agent.name]
        if agent.name == "world_scout_agent":
            runtime_names.append("research_agent")
        if agent.name == "factcheck_agent":
            runtime_names.append("factcheck_agent")
        if agent.name == "editor_in_chief":
            runtime_names.extend(["editor_agent", "chief_editor_agent"])
        runs = db.execute(
            select(AgentRun).where(AgentRun.agent_name.in_(runtime_names), AgentRun.started_at >= start)
        ).scalars().all()
        usage = daily_agent_usage(db, agent.id)
        completed = len([run for run in runs if run.status in {"completed", "completed_with_warnings"}])
        last_error = next((run.error_message for run in reversed(runs) if run.error_message), "")
        rows.append(
            {
                "id": agent.id,
                "name": agent.name,
                "title": agent.title,
                "status": agent.status,
                "runs_today": len(runs),
                "success_rate": round(completed / len(runs), 3) if runs else 0,
                "avg_duration_seconds": 0,
                "tokens_today": usage["tokens"],
                "cost_today": usage["cost"],
                "last_error": last_error,
                "current_issue": None,
            }
        )
    return rows


@router.get("/agents/{agent_id}/detail", response_model=None)
def agent_detail(agent_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    agent = db.get(OrgAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    config = db.execute(select(AgentConfig).where(AgentConfig.org_agent_id == agent.id)).scalar_one_or_none()
    prompt = None
    if config:
        prompt = resolve_prompt_template(db, agent, config)
    runtime_names = [agent.name]
    if agent.name == "world_scout_agent":
        runtime_names.append("research_agent")
    if agent.name == "factcheck_agent":
        runtime_names.append("factcheck_agent")
    if agent.name == "editor_in_chief":
        runtime_names.extend(["editor_agent", "chief_editor_agent", "rewrite_agent"])
    runs = db.execute(select(AgentRun).where(AgentRun.agent_name.in_(runtime_names)).order_by(AgentRun.started_at.desc()).limit(25)).scalars().all()
    issues = db.execute(
        select(Issue)
        .where((Issue.owner_agent_id == agent.id) | (Issue.reviewer_agent_id == agent.id))
        .order_by(Issue.created_at.desc())
        .limit(25)
    ).scalars().all()
    decisions = db.execute(
        select(DecisionLog)
        .where(DecisionLog.issue_id.in_([issue.id for issue in issues] or [-1]))
        .order_by(DecisionLog.created_at.desc())
        .limit(25)
    ).scalars().all()
    activity = db.execute(
        select(ActivityEvent)
        .where((ActivityEvent.actor_id == agent.id) | ((ActivityEvent.entity_type == "org_agent") & (ActivityEvent.entity_id == agent.id)))
        .order_by(ActivityEvent.created_at.desc())
        .limit(25)
    ).scalars().all()
    telemetry = next((item for item in agents_telemetry(db) if item["id"] == agent.id), None)
    usage = daily_agent_usage(db, agent.id)
    return {
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "title": agent.title,
            "role": agent.role,
            "status": agent.status,
            "description": agent.description,
            "responsibilities": agent.responsibilities,
            "budget_daily": agent.budget_daily,
            "token_limit_daily": agent.token_limit_daily,
            "last_heartbeat_at": agent.last_heartbeat_at,
        },
        "telemetry": telemetry,
        "config": agent_config_payload(config) if config else None,
        "prompt_template": prompt_payload(prompt) if prompt else None,
        "recent_agent_runs": [
            {
                "id": run.id,
                "agent_name": run.agent_name,
                "task_type": run.task_type,
                "status": run.status,
                "provider": run.provider,
                "model": run.model,
                "tokens_input": run.tokens_input,
                "tokens_output": run.tokens_output,
                "estimated_cost": run.estimated_cost,
                "error_message": run.error_message,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
            }
            for run in runs
        ],
        "recent_issues": [issue_payload(issue) for issue in issues],
        "recent_decision_logs": [decision_payload(item) for item in decisions],
        "recent_activity": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "message": event.message,
                "created_at": event.created_at,
            }
            for event in activity
        ],
        "budget_usage": usage,
        "provider_readiness": provider_readiness(db, config),
    }


@router.get("/llm-models", response_model=None)
def list_llm_models(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    items = db.execute(select(LLMModel).order_by(LLMModel.provider, LLMModel.model)).scalars().all()
    visible = [item for item in items if item.provider != "local_ollama_optional"]
    payloads = [llm_model_payload(item) for item in visible]
    if not any(item["provider"] == "ollama" and item["model"] == "gemma4:e4b" for item in payloads):
        payloads.append(
            {
                "id": 0,
                "provider": "ollama",
                "model": "gemma4:e4b",
                "label": "Local Gemma 4 E4B via Ollama",
                "input_cost_per_1m": 0,
                "output_cost_per_1m": 0,
                "supports_tools": False,
                "supports_json_schema": True,
                "enabled": True,
            }
        )
    return payloads


@router.get("/agent-configs", response_model=None)
def list_agent_configs(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    items = db.execute(select(AgentConfig).order_by(AgentConfig.org_agent_id)).scalars().all()
    return [agent_config_payload(item) for item in items]


@router.patch("/agent-configs/{config_id}", response_model=None)
def update_agent_config(config_id: int, payload: AgentConfigUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(AgentConfig, config_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Agent config not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="agent_config_updated",
        entity_type="agent_config",
        entity_id=item.id,
        message=f"Agent config updated for org agent #{item.org_agent_id}",
    )
    db.commit()
    return agent_config_payload(item)


@router.post("/agent-configs/{config_id}/test", response_model=None)
def test_agent_config(config_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(AgentConfig, config_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Agent config not found")
    settings = get_settings(db)
    provider_name = "mock" if settings["system_mode"] == "mock" else item.provider
    model = "mock" if provider_name == "mock" else item.model
    try:
        if settings["system_mode"] != "mock":
            assert_provider_allowed(db, provider_name, operator_path=True)
        api_key = None
        if provider_name in PROVIDER_SECRET_NAMES:
            api_key = resolve_secret_value(db, provider_name, PROVIDER_SECRET_NAMES[provider_name])
        provider = provider_for_name(provider_name, model=model, temperature=item.temperature, max_tokens=min(item.max_tokens, 128), api_key=api_key)
        response = provider.generate_structured(
            system_prompt=item.system_prompt or "ERA agent config test.",
            user_prompt="Return {\"ok\": true}.",
            output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False},
            model=model,
            temperature=0,
            max_tokens=64,
            tools=item.tools_json,
            timeout_seconds=item.timeout_seconds,
        )
        ok = True
        error = ""
        result = {"provider": response.provider, "model": response.model, "usage": response.usage.__dict__, "external_call": settings["system_mode"] != "mock"}
        db.add(
            CostEvent(
                agent_id=item.org_agent_id,
                task_type="agent_config_test",
                provider=response.provider,
                model=response.model,
                tokens_input=response.usage.tokens_input,
                tokens_output=response.usage.tokens_output,
                estimated_cost=response.usage.estimated_cost,
            )
        )
    except Exception as exc:
        ok = False
        error = str(exc)
        result = {"provider": provider_name, "model": model}
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="agent_config_test_success" if ok else "agent_config_test_failed",
        entity_type="agent_config",
        entity_id=item.id,
        message=f"Agent config test {'success' if ok else 'failed'} for #{item.id}: {error}",
    )
    db.commit()
    return {"ok": ok, "error": error, "result": result, "config": agent_config_payload(item)}


@router.get("/agent-configs/role-files/preview", response_model=None)
def preview_agent_role_files(db: Session = Depends(get_db)) -> dict[str, Any]:
    return role_file_preview(db)


@router.post("/agent-configs/role-files/apply", response_model=None)
def apply_agent_role_files_route(payload: ApplyAgentRoleFilesRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    result = apply_agent_role_files(db, confirm=payload.confirm)
    if payload.confirm and result.get("ok"):
        log_activity(
            db,
            actor_type="human",
            actor_id=None,
            event_type="agent_role_files_applied",
            entity_type="agent_config",
            entity_id=None,
            message=f"Applied role-file prompts to {len(result.get('applied') or [])} agents.",
            metadata={"version": result.get("version"), "applied": result.get("applied")},
        )
        db.commit()
    else:
        db.rollback()
    return result


@router.post("/agent-configs/content-agents/openai", response_model=None)
def configure_content_agents_for_openai(payload: BulkOpenAIContentAgentsRequest | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    secret = get_secret_row(db, "openai", "OPENAI_API_KEY")
    if secret is None or secret.status not in {"configured", "verified"}:
        raise HTTPException(status_code=422, detail="OpenAI ключ не добавлен. Сначала сохраните ключ в Интеграциях.")
    integration = db.execute(select(Integration).where(Integration.provider == "openai")).scalars().first()
    requested_model = payload.model if payload else None
    model = requested_model or ((integration.config_json or {}).get("model") if integration else None) or "gpt-4.1-mini"
    llm_model = db.execute(
        select(LLMModel).where(LLMModel.provider == "openai", LLMModel.model == model, LLMModel.enabled == True)  # noqa: E712
    ).scalar_one_or_none()
    if llm_model is None:
        raise HTTPException(status_code=422, detail=f"Модель OpenAI недоступна в списке llm_models: {model}")

    target_org_names = ["world_scout_agent", "factcheck_agent", "editor_in_chief"]
    runtime_agents = ["Research Agent", "Factcheck Agent", "Editor Agent", "Chief Editor Agent"]
    affected: list[dict[str, Any]] = []
    for name in target_org_names:
        agent = db.execute(select(OrgAgent).where(OrgAgent.name == name)).scalar_one_or_none()
        if agent is None:
            continue
        if agent.status != "disabled":
            agent.status = "idle"
        agent.budget_daily = max(float(agent.budget_daily or 0), 100.0)
        agent.token_limit_daily = max(int(agent.token_limit_daily or 0), 5000000)
        config = db.execute(select(AgentConfig).where(AgentConfig.org_agent_id == agent.id)).scalar_one_or_none()
        if config is None:
            config = AgentConfig(org_agent_id=agent.id)
            db.add(config)
            db.flush()
        config.provider = "openai"
        config.model = model
        config.enabled = True
        config.max_runs_per_day = max(int(config.max_runs_per_day or 0), 1000)
        config.timeout_seconds = max(int(config.timeout_seconds or 0), 45)
        config.daily_budget_usd = max(float(config.daily_budget_usd or 0), 100.0)
        config.daily_token_limit = max(int(config.daily_token_limit or 0), 5000000)
        affected.append({"agent_id": agent.id, "agent_name": agent.name, "config_id": config.id, "provider": config.provider, "model": config.model})

    publisher = db.execute(select(OrgAgent).where(OrgAgent.name == "publisher_agent")).scalar_one_or_none()
    if publisher is not None:
        publisher.status = "disabled"
        publisher.can_publish = False
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="content_agents_openai_configured",
        entity_type="agent_config",
        entity_id=None,
        message=f"Content agents configured for OpenAI dry-run with {model}.",
        metadata={"provider": "openai", "model": model, "affected": affected, "runtime_agents": runtime_agents, "publisher_disabled": True},
    )
    db.commit()
    return {"ok": True, "provider": "openai", "model": model, "affected": affected, "runtime_agents": runtime_agents, "publisher_disabled": True}


@router.get("/prompt-templates", response_model=None)
def list_prompt_templates(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    items = db.execute(select(PromptTemplate).order_by(PromptTemplate.agent_type, PromptTemplate.version.desc())).scalars().all()
    return [prompt_payload(item) for item in items]


@router.post("/prompt-templates", response_model=None)
def create_prompt_template(payload: PromptTemplateCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    latest = db.scalar(
        select(func.coalesce(func.max(PromptTemplate.version), 0)).where(PromptTemplate.name == payload.name, PromptTemplate.agent_type == payload.agent_type)
    ) or 0
    item = PromptTemplate(
        name=payload.name,
        agent_type=payload.agent_type,
        version=int(latest) + 1,
        content=payload.content,
        variables_json=payload.variables_json,
        status=payload.status,
    )
    db.add(item)
    db.flush()
    if item.status == "active":
        db.execute(
            select(PromptTemplate).where(PromptTemplate.agent_type == item.agent_type, PromptTemplate.id != item.id)
        )
        for other in db.execute(select(PromptTemplate).where(PromptTemplate.agent_type == item.agent_type, PromptTemplate.id != item.id)).scalars():
            other.status = "archived"
    log_activity(db, actor_type="human", actor_id=None, event_type="prompt_template_created", entity_type="prompt_template", entity_id=item.id, message=f"Prompt template created: {item.name} v{item.version}")
    db.commit()
    return prompt_payload(item)


@router.patch("/prompt-templates/{template_id}", response_model=None)
def update_prompt_template(template_id: int, payload: PromptTemplateUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(PromptTemplate, template_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    data = payload.model_dump(exclude_unset=True)
    if "content" in data and data["content"] != item.content:
        item = PromptTemplate(
            name=item.name,
            agent_type=item.agent_type,
            version=item.version + 1,
            content=data["content"],
            variables_json=data.get("variables_json", item.variables_json),
            status=data.get("status", "draft"),
        )
        db.add(item)
        db.flush()
    else:
        for key, value in data.items():
            setattr(item, key, value)
    if item.status == "active":
        for other in db.execute(select(PromptTemplate).where(PromptTemplate.agent_type == item.agent_type, PromptTemplate.id != item.id)).scalars():
            other.status = "archived"
    log_activity(db, actor_type="human", actor_id=None, event_type="prompt_template_updated", entity_type="prompt_template", entity_id=item.id, message=f"Prompt template updated: {item.name} v{item.version}")
    db.commit()
    return prompt_payload(item)


@router.get("/explain/{entity_type}/{entity_id}", response_model=None)
def explain_entity(entity_type: str, entity_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    decisions = db.execute(
        select(DecisionLog).where(DecisionLog.entity_type == entity_type, DecisionLog.entity_id == entity_id).order_by(DecisionLog.created_at.desc())
    ).scalars().all()
    runs: list[AgentRun] = []
    source_input: dict[str, Any] = {}
    if entity_type == "post":
        post = db.get(Post, entity_id)
        if post:
            source_input = {"post": {"id": post.id, "title": post.title, "status": post.status, "risk_score": post.risk_score, "quality_score": post.quality_score}, "source_urls": post.source_urls}
            runs = db.execute(select(AgentRun).where(AgentRun.input_json["topic_id"].as_integer() == post.topic_id).order_by(AgentRun.started_at)).scalars().all() if post.topic_id else []
    elif entity_type == "topic":
        topic = db.get(Topic, entity_id)
        if topic:
            source_input = {"topic": {"id": topic.id, "title": topic.title, "url": topic.url, "status": topic.status, "why_this_matters": topic.why_this_matters, "suggested_angle": topic.suggested_angle}}
            runs = db.execute(select(AgentRun).where(AgentRun.input_json["topic_id"].as_integer() == topic.id).order_by(AgentRun.started_at)).scalars().all()
    elif entity_type == "issue":
        issue = db.get(Issue, entity_id)
        if issue:
            source_input = {"issue": issue_payload(issue)}
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "source_input": source_input,
        "agent_chain": [
            {
                "agent": run.agent_name,
                "task_type": run.task_type,
                "status": run.status,
                "provider": run.provider,
                "model": run.model,
                "prompt_template_id": run.prompt_template_id,
                "prompt_version": run.prompt_version,
                "tokens_input": run.tokens_input,
                "tokens_output": run.tokens_output,
            }
            for run in runs
        ],
        "decisions": [decision_payload(item) for item in decisions],
    }


@router.get("/ui/button-contracts", response_model=None)
def button_contracts() -> list[dict[str, Any]]:
    now = datetime.now(UTC).isoformat()

    def item(page: str, label: str, component_id: str, endpoint: str, method: str, payload_schema: dict[str, Any], state: str, creates_activity: bool, implemented: bool = True) -> dict[str, Any]:
        return {
            "page": page,
            "label": label,
            "component_id": component_id,
            "endpoint": endpoint,
            "method": method,
            "action_type": "client" if method in {"CLIENT", "NAVIGATE"} else "api",
            "payload_schema": payload_schema,
            "expected_success_status": 200,
            "expected_state_change": state,
            "creates_activity_event": creates_activity,
            "implemented": implemented,
            "last_tested_at": now,
        }

    return [
        item("Global", "Создать тему", "command_bar.create_topic", "/topics#create-topic", "NAVIGATE", {}, "opens create topic form", False),
        item("Global", "Запустить dry-run", "command_bar.open_dry_run", "/topics", "NAVIGATE", {}, "opens topic dry-run actions", False),
        item("Global", "Проверить систему", "command_bar.readiness", "/#readiness", "NAVIGATE", {}, "opens readiness panel", False),
        item("Dashboard", "Проверить OpenAI", "dashboard.test_openai", "/api/secrets/openai/OPENAI_API_KEY/test", "POST", {}, "provider_test_succeeded/failed; disabled in mock", True),
        item("Dashboard", "Применить OpenAI", "dashboard.bulk_openai", "/api/agent-configs/content-agents/openai", "POST", {"model": "string|null"}, "content_agents_openai_configured", True),
        item("Dashboard", "Запустить dry-run", "dashboard.run_dry_run", "/api/topics/{id}/run-dry-run", "POST", {}, "dry_run post in review; disabled until ready", True),
        item("Dashboard", "Создать план дня", "dashboard.ceo_create_daily_plan", "/api/operating-loop/run", "POST", {"action": "create_daily_plan", "mode": "manual_run"}, "operating_loop_run + issues", True),
        item("Dashboard", "Обновить Kanban", "dashboard.ceo_refresh_kanban", "/api/operating-loop/run", "POST", {"action": "refresh_kanban", "mode": "manual_run"}, "operating_loop_run + issue updates", True),
        item("Dashboard", "Проверить блокировки", "dashboard.ceo_check_blockers", "/api/operating-loop/run", "POST", {"action": "check_blockers", "mode": "manual_run"}, "operating_loop_run + blocker report", True),
        item("Dashboard", "Создать демо", "dashboard.create_demo", "/api/dev/demo-data", "POST", {}, "demo topic/post/source", True),
        item("Dashboard", "Очистить демо", "dashboard.clear_demo", "/api/dev/demo-data", "DELETE", {}, "demo data removed only", True),
        item("Dashboard", "Pause all agents", "dashboard.pause_agents", "/api/system/pause-agents", "POST", {}, "non-disabled agents paused", True),
        item("Dashboard", "Pause all routines", "dashboard.pause_routines", "/api/system/pause-routines", "POST", {}, "routines disabled", True),
        item("Agents", "Конфиг", "agents.config", "/agents/{id}", "NAVIGATE", {}, "opens agent detail page", False, True),
        item("Agents", "Настроить content agents для OpenAI dry-run", "agents.bulk_openai", "/api/agent-configs/content-agents/openai", "POST", {"model": "string|null"}, "content_agents_openai_configured; Publisher remains disabled", True),
        item("Agents", "Возобновить", "agents.resume", "/api/org/agents/{id}/status", "PATCH", {"status": "idle"}, "agent status -> idle", True),
        item("Agents", "Пауза", "agents.pause", "/api/org/agents/{id}/status", "PATCH", {"status": "paused"}, "agent status -> paused", True),
        item("Agent Detail", "Сохранить", "agent_detail.save_config", "/api/agent-configs/{id}", "PATCH", {"provider": "string", "model": "string", "max_runs_per_day": "number"}, "agent_config_updated", True),
        item("Agent Detail", "Тест агента", "agent_detail.test_agent", "/api/agent-configs/{id}/test", "POST", {}, "agent_config_test_success/failed", True),
        item("Prompts", "Сохранить", "prompts.save", "/api/prompt-templates/{id}", "PATCH", {"content": "string", "status": "draft|active|archived"}, "prompt_template_updated", True),
        item("Issues", "Открыть", "issues.open", "client state", "CLIENT", {}, "details panel opens", False, True),
        item("Issues", "status transition", "issues.move_status", "/api/issues/{id}", "PATCH", {"status": "backlog|ready|in_progress|review|waiting_human|completed|failed|cancelled"}, "issue_transitioned or issue_transition_rejected", True),
        item("Issues", "Решения", "issues.decisions", "/api/decision-logs?issue_id={id}", "GET", {}, "decision logs loaded", False, True),
        item("Topics", "Черновик", "topics.generate_draft", "/api/topics/{id}/run-pipeline", "POST", {}, "issue/task/post/decision logs", True),
        item("Topics", "LLM dry-run", "topics.real_llm_dry_run", "/api/topics/{id}/run-dry-run", "POST", {"channel_id": "int|null"}, "real LLM agent runs + dry_run post in review", True),
        item("Topics", "На проверку", "topics.human_review", "/api/topics/{id}", "PATCH", {"status": "needs_human_review"}, "topic_updated", True),
        item("Topics", "Логи", "topics.logs", "/api/agent-runs?topic_id={id}", "GET", {}, "agent runs loaded", False, True),
        item("Topics", "Почему?", "topics.explain", "/api/explain/topic/{id}", "GET", {}, "explanation loaded", False, True),
        item("Topics", "Отклонить", "topics.reject", "/api/topics/{id}", "PATCH", {"status": "rejected"}, "topic_updated", True),
        item("Posts", "Сохранить", "posts.save", "/api/posts/{id}", "PATCH", {"title": "string", "body": "string"}, "post_edited", True),
        item("Posts", "Одобрить", "posts.approve", "/api/posts/{id}/approve", "POST", {}, "post approved/task log", True),
        item("Posts", "Запланировать", "posts.schedule", "/api/posts/{id}/schedule", "POST", {"scheduled_at": "datetime|null"}, "post scheduled/task log", True),
        item("Posts", "Переписать", "posts.rewrite", "/api/posts/{id}/rewrite", "POST", {"notes": "string[]"}, "post version increments/task log", True),
        item("Posts", "Копировать", "posts.copy", "clipboard", "CLIENT", {}, "text copied", False, True),
        item("Posts", "Архив", "posts.archive", "/api/posts/{id}/archive", "POST", {}, "post_archived", True),
        item("Posts", "Отклонить", "posts.reject", "/api/posts/{id}/reject", "POST", {}, "post rejected", True),
        item("Posts", "Как это создано?", "posts.explain", "/api/explain/post/{id}", "GET", {}, "explanation loaded", False, True),
        item("Integrations", "Сохранить", "integrations.save", "/api/integrations/{id}", "PATCH", {"config_json": "object"}, "integration_updated", True),
        item("Integrations", "Проверить", "integrations.test", "/api/integrations/{id}/test", "POST", {}, "last_check/status/activity", True),
        item("Integrations", "Тест админу", "integrations.admin_test", "/api/integrations/{id}/test-admin-message", "POST", {}, "notification/activity", True),
        item("Integrations", "Скопировать env-шаблон", "integrations.copy_env", "clipboard", "CLIENT", {}, "env template copied", False, True),
        item("Channels", "Сохранить канал", "channels.save", "/api/channels/{id}", "PATCH", {"name": "string"}, "channel_updated", True),
        item("Channels", "Сохранить MAX", "channels.save_max", "/api/platform-channels/{id}", "PATCH", {"external_chat_id": "string"}, "platform_channel_updated", True),
        item("Channels", "Тест связи", "channels.test_max", "/api/platform-channels/{id}/test", "POST", {}, "platform status/activity", True),
        item("Sources", "Добавить источник", "sources.create", "/api/sources", "POST", {"name": "string", "url": "string"}, "source_created", True),
        item("Sources", "Сохранить", "sources.save", "/api/sources/{id}", "PATCH", {"trust_score": "number", "channel_ids": "number[]"}, "source_updated", True),
        item("Sources", "Health", "sources.health", "/api/sources/{id}/health-check", "POST", {}, "source_health_checked", True),
        item("Sources", "Удалить", "sources.delete", "/api/sources/{id}", "DELETE", {}, "source_deleted", True),
        item("Routines", "Сохранить", "routines.save", "/api/routines/{id}", "PATCH", {"cron_schedule": "string"}, "routine_updated", True),
        item("Routines", "Dry run", "routines.dry_run", "/api/routines/{id}/dry-run", "POST", {}, "routine_dry_run", True),
        item("Routines", "Разово", "routines.run_once", "/api/routines/{id}/run-once", "POST", {}, "routine_triggered or routine_blocked", True),
        item("Calendar", "Перенести", "calendar.reschedule", "/api/posts/{id}/schedule", "POST", {"scheduled_at": "datetime"}, "post scheduled/task log", True),
        item("Calendar", "Снять", "calendar.unschedule", "/api/posts/{id}/unschedule", "POST", {}, "post_unscheduled", True),
        item("Notifications", "Прочитано", "notifications.read", "/api/notifications/{id}/read", "POST", {}, "notification_read", True),
        item("Notifications", "Открыть связанную сущность", "notifications.open_entity", "client navigation", "NAVIGATE", {}, "related page opens", False, True),
        item("Activity", "Применить", "activity.apply_filters", "/api/activity", "GET", {"event_type": "optional", "agent_id": "optional", "entity_type": "optional"}, "filtered activity loaded", False, True),
    ]


@router.get("/events/stream")
def events_stream(last_id: int = 0):
    def stream():
        current_id = last_id
        while True:
            with SessionLocal() as db:
                events = db.execute(
                    select(ActivityEvent).where(ActivityEvent.id > current_id).order_by(ActivityEvent.id).limit(20)
                ).scalars().all()
                for event in events:
                    current_id = event.id
                    yield f"id: {event.id}\nevent: activity_event_created\ndata: {event.message}\n\n"
                unread = db.scalar(select(func.count()).select_from(Notification).where(Notification.status == "unread")) or 0
                yield f"event: notification_count\ndata: {int(unread)}\n\n"
            time.sleep(2)

    return StreamingResponse(stream(), media_type="text/event-stream")
