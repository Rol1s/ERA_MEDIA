"""Morning source scan fallback service."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from app.models.all_models import Source


class MorningSourceScanService:
    def __init__(self, db: Session):
        self.db = db

    def run(self, *, max_sources: int = 20, limit_per_source: int = 3) -> dict[str, Any]:
        sources = self.db.query(Source).limit(max_sources).all()
        return {
            "ok": True,
            "sources_scanned": len(sources),
            "limit_per_source": limit_per_source,
            "summary": "Morning source scan fallback completed.",
            "items": [],
        }
