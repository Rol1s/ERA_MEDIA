"""Lightweight editorial dedupe helpers.

The imported publication package references this module but did not ship it.
This deterministic fallback is intentionally conservative: it only links very
similar recent topics and never deletes or suppresses content by itself.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import Topic


def _norm(text: str | None) -> str:
    text = (text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^\wа-яё]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_matching_topic(db: Session, topic: Topic, threshold: float = 0.82) -> tuple[Topic | None, float, str]:
    title = _norm(getattr(topic, "title", ""))
    if not title:
        return None, 0.0, "empty_title"
    candidates = list(
        db.execute(
            select(Topic)
            .where(Topic.id != getattr(topic, "id", None))
            .order_by(Topic.id.desc())
            .limit(100)
        ).scalars()
    )
    best: Topic | None = None
    best_score = 0.0
    for candidate in candidates:
        score = _similarity(title, _norm(getattr(candidate, "title", "")))
        if score > best_score:
            best = candidate
            best_score = score
    if best is not None and best_score >= threshold:
        return best, best_score, "title_similarity"
    return None, best_score, "no_match"
