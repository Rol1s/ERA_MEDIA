"""Agent role-file helpers fallback."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session


def role_file_preview(db: Session) -> dict[str, Any]:
    return {"ok": True, "files": [], "note": "role-file generation not configured in local fallback"}


def apply_agent_role_files(db: Session, *, confirm: bool = False) -> dict[str, Any]:
    return {"ok": bool(confirm), "applied": [], "skipped": True, "note": "no role files written by fallback"}
