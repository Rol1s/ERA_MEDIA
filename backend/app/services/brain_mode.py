"""Local brain-mode policy fallback."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session


def active_brain(db: Session | None = None) -> dict[str, Any]:
    return {"mode": "default", "provider_policy": "allow_configured"}


def assert_provider_allowed(db: Session, provider_name: str, *, operator_path: bool = False) -> None:
    # Conservative fallback: do not block configured provider checks in local/dev mode.
    return None
