from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm_provider import LLMConfigurationError, provider_for_name
from app.db.session import get_db
from app.models.all_models import CostEvent, Integration, LLMModel
from app.services.notifications import create_notification
from app.services.org import log_activity
from app.services.secrets import (
    PROVIDER_SECRET_NAMES,
    SecretStoreError,
    decrypt_secret,
    disable_secret,
    get_secret_row,
    list_secret_status,
    safe_secret_payload,
    upsert_secret,
)
from app.services.settings import get_settings

router = APIRouter()
MAX_DEFAULT_BASE_URL = "https://platform-api.max.ru"


class SecretUpdate(BaseModel):
    secret_value: str


def _max_get_me(base_url: str, token: str) -> dict[str, Any]:
    import urllib.error
    import urllib.request

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


def _safe_error(error: Exception) -> str:
    text = str(error)
    for marker in ["sk-", "AIza", "xox", "eyJ"]:
        if marker in text:
            return "Provider test failed with a secret-bearing error. Check server logs/provider settings."
    return text[:500]


def _configured_test_model(db: Session, provider: str) -> str:
    defaults = {
        "openai": "gpt-4.1-mini",
        "anthropic": "claude-3-5-haiku-latest",
        "gemini": "gemini-2.5-flash",
    }
    integration = db.execute(select(Integration).where(Integration.provider == provider)).scalars().first()
    configured = (integration.config_json or {}).get("model") if integration else None
    enabled = {
        item.model
        for item in db.execute(select(LLMModel).where(LLMModel.provider == provider, LLMModel.enabled == True)).scalars()  # noqa: E712
    }
    if configured and configured in enabled:
        return configured
    return defaults[provider]


def _estimate_cost(db: Session, provider: str, model: str, tokens_input: int, tokens_output: int) -> float:
    row = db.execute(select(LLMModel).where(LLMModel.provider == provider, LLMModel.model == model)).scalar_one_or_none()
    if row is None:
        return 0.0
    return round((tokens_input / 1_000_000 * row.input_cost_per_1m) + (tokens_output / 1_000_000 * row.output_cost_per_1m), 8)


@router.get("/status", response_model=None)
def status(db: Session = Depends(get_db)) -> dict[str, Any]:
    return list_secret_status(db)


@router.post("/{provider}/{secret_name}", response_model=None)
def save_secret(provider: str, secret_name: str, payload: SecretUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        row = upsert_secret(db, provider, secret_name, payload.secret_value)
    except SecretStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="secret_updated",
        entity_type="integration_secret",
        entity_id=row.id,
        message=f"Secret updated: {provider}/{secret_name}",
        metadata={"provider": provider, "secret_name": secret_name, "masked_value": row.masked_value},
    )
    db.commit()
    db.refresh(row)
    return safe_secret_payload(row, provider, secret_name)


@router.delete("/{provider}/{secret_name}", response_model=None)
def delete_secret(provider: str, secret_name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        row = disable_secret(db, provider, secret_name)
    except SecretStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if row:
        log_activity(
            db,
            actor_type="human",
            actor_id=None,
            event_type="secret_deleted",
            entity_type="integration_secret",
            entity_id=row.id,
            message=f"Secret deleted: {provider}/{secret_name}",
            metadata={"provider": provider, "secret_name": secret_name},
        )
    db.commit()
    return safe_secret_payload(row, provider, secret_name)


@router.post("/{provider}/{secret_name}/test", response_model=None)
def test_secret(provider: str, secret_name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = get_settings(db)
    if settings["system_mode"] == "mock":
        raise HTTPException(status_code=422, detail="Переключите систему в dry_run для проверки реального провайдера.")
    row = get_secret_row(db, provider, secret_name)
    if row is None or row.status not in {"configured", "verified", "failed"}:
        raise HTTPException(status_code=422, detail="Secret is not configured")
    row.last_test_at = datetime.now(UTC)
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="provider_test_started",
        entity_type="integration_secret",
        entity_id=row.id,
        message=f"Provider test started: {provider}/{secret_name}",
        metadata={"provider": provider, "secret_name": secret_name},
    )
    db.commit()

    ok = False
    error = ""
    result: dict[str, Any] = {}
    try:
        secret_value = decrypt_secret(row.encrypted_value)
        if provider in {"openai", "anthropic", "gemini"}:
            model = _configured_test_model(db, provider)
            llm = provider_for_name(provider, model=model, api_key=secret_value)
            response = llm.generate_structured(
                system_prompt="Return a tiny JSON health check.",
                user_prompt="Return {\"ok\": true}.",
                output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False},
                model=model,
                temperature=0,
                max_tokens=64,
                timeout_seconds=20,
            )
            estimated_cost = response.usage.estimated_cost or _estimate_cost(
                db,
                response.provider,
                response.model,
                response.usage.tokens_input,
                response.usage.tokens_output,
            )
            db.add(
                CostEvent(
                    task_type="secret_provider_test",
                    provider=response.provider,
                    model=response.model,
                    tokens_input=response.usage.tokens_input,
                    tokens_output=response.usage.tokens_output,
                    estimated_cost=estimated_cost,
                )
            )
            result = {
                "provider": response.provider,
                "model": response.model,
                "usage": {
                    "tokens_input": response.usage.tokens_input,
                    "tokens_output": response.usage.tokens_output,
                    "estimated_cost": estimated_cost,
                },
                "structured": response.structured,
            }
            ok = True
        elif provider == "max":
            result = _max_get_me(MAX_DEFAULT_BASE_URL, secret_value)
            ok = bool(result.get("ok"))
            if not ok:
                error = f"MAX /me check failed: HTTP {result.get('status')}"
        else:
            raise LLMConfigurationError("Unsupported provider")
    except Exception as exc:
        error = _safe_error(exc)

    row.status = "configured" if ok else "failed"
    row.last_success_at = datetime.now(UTC) if ok else row.last_success_at
    row.last_error = "" if ok else error
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="provider_test_succeeded" if ok else "provider_test_failed",
        entity_type="integration_secret",
        entity_id=row.id,
        message=f"Provider test {'succeeded' if ok else 'failed'}: {provider}/{secret_name}",
        metadata={"provider": provider, "secret_name": secret_name, "ok": ok},
    )
    if not ok:
        create_notification(
            db,
            severity="warning",
            title="Проверка provider не прошла",
            message=error,
            entity_type="integration_secret",
            entity_id=row.id,
        )
    db.commit()
    return {"ok": ok, "error": error, "result": result, "secret": safe_secret_payload(row, provider, secret_name)}
