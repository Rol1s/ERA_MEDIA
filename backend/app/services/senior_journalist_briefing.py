"""Senior journalist briefing fallback service."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session


class SeniorJournalistBriefingService:
    def __init__(self, db: Session):
        self.db = db

    def run(self, *, max_items: int = 160, target_topics: int = 15) -> dict[str, Any]:
        return {
            "ok": True,
            "summary": "Повестка собрана в fallback-режиме: подключите полноценный briefing service для расширенной редакторской выборки.",
            "messages": [
                {
                    "role": "assistant",
                    "content": "Повестка готова в fallback-режиме. Новые источники можно обработать через newsroom/API.",
                }
            ],
            "max_items": max_items,
            "target_topics": target_topics,
        }
