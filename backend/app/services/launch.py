"""Manual launch helpers fallback."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.all_models import Post


def mark_published_manually(
    db: Session,
    post: Post,
    *,
    published_at: datetime | None = None,
    published_url: str = "",
    note: str = "",
) -> Post:
    post.status = "published"
    if hasattr(post, "published_at"):
        post.published_at = published_at or datetime.now(timezone.utc)
    if hasattr(post, "published_url"):
        post.published_url = published_url or ""
    if hasattr(post, "manual_publish_note"):
        post.manual_publish_note = note or ""
    db.add(post)
    db.flush()
    return post
