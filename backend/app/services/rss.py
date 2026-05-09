from datetime import UTC, datetime
from typing import Any

import feedparser
from sqlalchemy.orm import Session

from app.models.all_models import Source, Topic


def collect_source_items(db: Session, source: Source, *, max_items: int = 20) -> list[Topic]:
    if source.type == "manual":
        return []
    if source.type not in {"rss", "website", "ladder_optional"}:
        return []

    feed: Any = feedparser.parse(source.url)
    created: list[Topic] = []
    for entry in feed.entries[:max_items]:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", None)
        if not title:
            continue
        topic = Topic(
            source_id=source.id,
            title=title,
            url=link,
            raw_text=getattr(entry, "summary", "") or "",
            summary=getattr(entry, "summary", "") or title,
            published_at=None,
            status="new",
            source_trust_score=source.trust_score,
        )
        db.add(topic)
        created.append(topic)
    source.last_checked_at = datetime.now(UTC)
    db.commit()
    return created

