from __future__ import annotations

from urllib.parse import urlparse


def is_feed_url(url: str) -> bool:
    clean = (url or "").strip().lower()
    if not clean:
        return False
    parsed = urlparse(clean)
    path = parsed.path or ""
    if path.endswith((".xml", ".rss", ".atom")):
        return True
    feed_markers = (
        "/rss",
        "/feed",
        "/feeds/",
        "/atom",
        "rss.",
        "feed.",
    )
    return any(marker in clean for marker in feed_markers)


def public_source_urls(
    urls: list[str] | tuple[str, ...] | None,
    *,
    limit: int = 5,
    allow_feed_fallback: bool = False,
) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in urls or []:
        url = str(raw or "").strip()
        if not url or url in seen or is_feed_url(url):
            continue
        seen.add(url)
        cleaned.append(url)
        if len(cleaned) >= limit:
            break
    if cleaned:
        return cleaned

    if not allow_feed_fallback:
        return []

    # Fallback for internal checks where the only source we have is an RSS/feed URL.
    fallback: list[str] = []
    for raw in urls or []:
        url = str(raw or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        fallback.append(url)
        if len(fallback) >= limit:
            break
    return fallback
