from __future__ import annotations

import base64
import hashlib
import os
from datetime import UTC, datetime
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.all_models import Integration, IntegrationSecret

PROVIDER_SECRET_NAMES = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "max": "MAX_BOT_TOKEN",
}


class SecretStoreError(RuntimeError):
    pass


def secret_storage_ready() -> bool:
    return bool(settings.app_secret_key or os.getenv("APP_SECRET_KEY"))


def _fernet() -> Fernet:
    raw = settings.app_secret_key or os.getenv("APP_SECRET_KEY", "")
    if not raw:
        raise SecretStoreError("Хранилище секретов не настроено. Добавьте APP_SECRET_KEY на сервер.")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_value: str) -> str:
    try:
        return _fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretStoreError("Cannot decrypt stored secret. Check APP_SECRET_KEY.") from exc


def mask_secret(value: str, provider: str) -> str:
    compact = value.strip()
    last4 = compact[-4:] if len(compact) >= 4 else "****"
    if provider == "openai" and compact.startswith("sk-"):
        return f"sk-...{last4}"
    if provider == "anthropic" and compact.startswith("sk-ant-"):
        return f"sk-ant-...{last4}"
    if provider == "gemini" and compact.startswith("AI"):
        return f"AI...{last4}"
    return f"****{last4}"


def validate_secret(provider: str, secret_name: str, value: str) -> None:
    expected = PROVIDER_SECRET_NAMES.get(provider)
    if expected is None or secret_name != expected:
        raise SecretStoreError("Unsupported provider/secret name")
    cleaned = value.strip()
    if len(cleaned) < 12:
        raise SecretStoreError("Secret value is too short")
    if "\n" in cleaned or "\r" in cleaned:
        raise SecretStoreError("Secret value must be a single line")


def get_secret_row(db: Session, provider: str, secret_name: str) -> IntegrationSecret | None:
    return db.execute(
        select(IntegrationSecret).where(
            IntegrationSecret.provider == provider,
            IntegrationSecret.secret_name == secret_name,
        )
    ).scalar_one_or_none()


def safe_secret_payload(row: IntegrationSecret | None, provider: str, secret_name: str) -> dict[str, Any]:
    if row is None or row.status in {"missing", "disabled"}:
        return {
            "provider": provider,
            "secret_name": secret_name,
            "status": "missing" if row is None else row.status,
            "masked_value": "",
            "last_test_at": row.last_test_at if row else None,
            "last_success_at": row.last_success_at if row else None,
            "last_error": row.last_error if row else "",
        }
    return {
        "provider": row.provider,
        "secret_name": row.secret_name,
        "status": row.status,
        "masked_value": row.masked_value,
        "last_test_at": row.last_test_at,
        "last_success_at": row.last_success_at,
        "last_error": row.last_error,
    }


def list_secret_status(db: Session) -> dict[str, Any]:
    providers = []
    for provider, secret_name in PROVIDER_SECRET_NAMES.items():
        providers.append(safe_secret_payload(get_secret_row(db, provider, secret_name), provider, secret_name))
    return {
        "storage_ready": secret_storage_ready(),
        "storage_error": "" if secret_storage_ready() else "Хранилище секретов не настроено. Добавьте APP_SECRET_KEY на сервер.",
        "providers": providers,
    }


def upsert_secret(db: Session, provider: str, secret_name: str, value: str) -> IntegrationSecret:
    validate_secret(provider, secret_name, value)
    encrypted = encrypt_secret(value.strip())
    existing = get_secret_row(db, provider, secret_name)
    integration = db.execute(select(Integration).where(Integration.provider == provider)).scalars().first()
    now = datetime.now(UTC)
    if existing is None:
        existing = IntegrationSecret(
            integration_id=integration.id if integration else None,
            provider=provider,
            secret_name=secret_name,
            encrypted_value=encrypted,
            masked_value=mask_secret(value, provider),
            status="configured",
            rotated_at=now,
        )
        db.add(existing)
    else:
        existing.integration_id = integration.id if integration else existing.integration_id
        existing.encrypted_value = encrypted
        existing.masked_value = mask_secret(value, provider)
        existing.status = "configured"
        existing.last_error = ""
        existing.rotated_at = now
    return existing


def disable_secret(db: Session, provider: str, secret_name: str) -> IntegrationSecret | None:
    row = get_secret_row(db, provider, secret_name)
    if row is None:
        return None
    row.encrypted_value = encrypt_secret("disabled")
    row.masked_value = ""
    row.status = "disabled"
    row.last_error = ""
    return row


def resolve_secret_value(db: Session | None, provider: str, env_name: str) -> str:
    if db is not None:
        row = get_secret_row(db, provider, env_name)
        if row is not None and row.status in {"configured", "verified"}:
            return decrypt_secret(row.encrypted_value)
    env_value = os.getenv(env_name)
    if env_value:
        return env_value
    label = provider.capitalize() if provider != "openai" else "OpenAI"
    raise SecretStoreError(f"Missing {label} API key")
