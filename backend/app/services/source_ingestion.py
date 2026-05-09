from __future__ import annotations

import hashlib
import html
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

import feedparser
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.all_models import Channel, Source, SourceChannelMap, SourceItem, Topic
from app.services.org import log_activity

USER_AGENT = "ERA-Media-Factory/0.1 (+source-ingestion; public pages only)"
MAX_BYTES = 1_500_000
MIN_TEXT_LENGTH = 420

BLOCKED_MARKERS = [
    "subscribe to continue",
    "sign in to continue",
    "log in to continue",
    "enable javascript",
    "paywall",
    "premium content",
    "для продолжения войдите",
    "оформите подписку",
    "только для подписчиков",
]


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    duration_ms: int
    error: str = ""


@dataclass
class ExtractedContent:
    title: str
    canonical_url: str
    summary: str
    text: str
    published_at: datetime | None
    language: str
    paywall_or_blocked_detected: bool
    status: str
    error: str = ""


@dataclass
class IngestionResult:
    source_id: int
    fetched_count: int = 0
    extracted_count: int = 0
    topics_created: int = 0
    duplicates: int = 0
    blocked: int = 0
    failed: int = 0
    source_item_ids: list[int] | None = None
    topic_ids: list[int] | None = None
    last_error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "fetched_count": self.fetched_count,
            "extracted_count": self.extracted_count,
            "topics_created": self.topics_created,
            "duplicates": self.duplicates,
            "blocked": self.blocked,
            "failed": self.failed,
            "source_item_ids": self.source_item_ids or [],
            "topic_ids": self.topic_ids or [],
            "last_error": self.last_error,
        }


class SimpleReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.capture_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.lang = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): (value or "") for key, value in attrs}
        if tag in {"script", "style", "noscript", "svg", "canvas", "form", "nav", "footer", "header", "aside"}:
            self.skip_depth += 1
            return
        if tag == "html":
            self.lang = attrs_dict.get("lang", "")
        if tag == "title":
            self.capture_title = True
        if tag == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content", "")
            if name and content:
                self.meta[name] = html.unescape(content.strip())
        if tag == "link" and attrs_dict.get("rel", "").lower() == "canonical":
            self.canonical = attrs_dict.get("href", "")
        if tag in {"p", "h1", "h2", "h3", "li", "blockquote"} and self.skip_depth == 0:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas", "form", "nav", "footer", "header", "aside"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "title":
            self.capture_title = False
        if tag in {"p", "h1", "h2", "h3", "li", "blockquote"} and self.skip_depth == 0:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.capture_title:
            self.title_parts.append(data)
        if self.skip_depth == 0:
            cleaned = " ".join(data.split())
            if len(cleaned) >= 2:
                self.text_parts.append(cleaned)


class HttpFetchService:
    def fetch(self, url: str, *, timeout_seconds: int = 12) -> FetchResult:
        started = time.perf_counter()
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.5"})
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raw = raw[:MAX_BYTES]
                content_type = response.headers.get("content-type", "")
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
                return FetchResult(
                    url=url,
                    final_url=response.geturl(),
                    status_code=getattr(response, "status", 200),
                    content_type=content_type,
                    text=text,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
        except Exception as exc:
            return FetchResult(
                url=url,
                final_url=url,
                status_code=0,
                content_type="",
                text="",
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
            )


class ContentExtractionService:
    def extract(self, html_text: str, base_url: str, *, fallback_title: str = "", fallback_summary: str = "", published_at: datetime | None = None) -> ExtractedContent:
        parser = SimpleReadableHTMLParser()
        try:
            parser.feed(html_text)
        except Exception:
            pass
        text = normalize_text("\n".join(parser.text_parts))
        title = normalize_text(parser.meta.get("og:title") or "".join(parser.title_parts) or fallback_title)
        summary = normalize_text(parser.meta.get("description") or parser.meta.get("og:description") or fallback_summary or summarize_text(text))
        canonical = normalize_url(urljoin(base_url, parser.canonical or parser.meta.get("og:url", "") or base_url))
        detected_date = parse_datetime(parser.meta.get("article:published_time") or parser.meta.get("date") or "") or published_at
        language = (parser.lang or "").split("-")[0].lower()
        blocked = detect_blocked(html_text, text)
        if blocked:
            status = "blocked"
            error = "Blocked/login/paywall-like page detected"
        elif len(text) < MIN_TEXT_LENGTH:
            status = "too_short"
            error = f"Extracted text is too short: {len(text)} chars"
        else:
            status = "extracted"
            error = ""
        return ExtractedContent(
            title=title[:500] or fallback_title[:500] or canonical,
            canonical_url=canonical,
            summary=summary[:1200],
            text=text,
            published_at=detected_date,
            language=language or detect_language(text),
            paywall_or_blocked_detected=blocked,
            status=status,
            error=error,
        )


class RssFetchService:
    def __init__(self, http: HttpFetchService | None = None, extractor: ContentExtractionService | None = None) -> None:
        self.http = http or HttpFetchService()
        self.extractor = extractor or ContentExtractionService()

    def fetch_items(self, source: Source, *, limit: int = 5, fetch_articles: bool = True) -> tuple[list[dict[str, Any]], FetchResult]:
        feed_result = self.http.fetch(source.url)
        if feed_result.error:
            return [], feed_result
        parsed = feedparser.parse(feed_result.text)
        items: list[dict[str, Any]] = []
        for entry in parsed.entries[:limit]:
            url = normalize_url(entry.get("link") or source.url)
            published_at = parse_datetime(entry.get("published") or entry.get("updated") or "")
            fallback_summary = normalize_text(entry.get("summary", ""))
            fallback_title = normalize_text(entry.get("title", ""))
            if fetch_articles and url:
                article_result = self.http.fetch(url)
                if article_result.error:
                    extracted = ExtractedContent(
                        title=fallback_title,
                        canonical_url=url,
                        summary=fallback_summary,
                        text=fallback_summary,
                        published_at=published_at,
                        language=source.language,
                        paywall_or_blocked_detected=False,
                        status="failed",
                        error=article_result.error,
                    )
                    raw_html = ""
                else:
                    extracted = self.extractor.extract(
                        article_result.text,
                        article_result.final_url or url,
                        fallback_title=fallback_title,
                        fallback_summary=fallback_summary,
                        published_at=published_at,
                    )
                    raw_html = article_result.text
            else:
                extracted = ExtractedContent(
                    title=fallback_title,
                    canonical_url=url,
                    summary=fallback_summary,
                    text=strip_tags(fallback_summary),
                    published_at=published_at,
                    language=source.language,
                    paywall_or_blocked_detected=False,
                    status="extracted" if len(fallback_summary) >= 160 else "too_short",
                    error="" if len(fallback_summary) >= 160 else "RSS summary is too short",
                )
                raw_html = fallback_summary
            items.append({"url": url, "extracted": extracted, "raw_html": raw_html})
        return items, feed_result


class DeduplicationService:
    def find_duplicate(self, db: Session, source: Source, *, url: str, canonical_url: str, title: str, raw_hash: str) -> SourceItem | None:
        title_key = normalize_title(title)
        since = datetime.now(UTC) - timedelta(hours=72)
        candidates = db.execute(
            select(SourceItem).where(
                or_(
                    SourceItem.url == url,
                    SourceItem.canonical_url == canonical_url,
                    SourceItem.raw_html_hash == raw_hash,
                    SourceItem.source_id == source.id,
                )
            ).order_by(SourceItem.id.desc()).limit(80)
        ).scalars().all()
        for item in candidates:
            if item.url == url or (canonical_url and item.canonical_url == canonical_url) or (raw_hash and item.raw_html_hash == raw_hash):
                return item
            if item.source_id == source.id and item.created_at >= since and title_similarity(title_key, normalize_title(item.title)) >= 0.84:
                return item
        return None


class TopicScoringService:
    def score(self, source: Source, item: SourceItem, channels: list[Channel]) -> dict[str, Any]:
        content_length_score = min(1.0, max(0.0, item.content_length / 2000))
        freshness_score = freshness(item.published_at or item.detected_at)
        source_trust = max(0.0, min(1.0, float(source.trust_score or 0.5)))
        usefulness = score_usefulness(item.extracted_text, item.title)
        risk = score_risk(item.extracted_text, channels)
        relevance = score_channel_relevance(item, channels)
        duplicate_penalty = 0.45 if item.duplicate_of_item_id else 0.0
        final = max(0.0, min(1.0, (freshness_score * 0.18 + source_trust * 0.18 + content_length_score * 0.16 + usefulness * 0.22 + relevance * 0.18 + (1 - risk) * 0.08) - duplicate_penalty))
        return {
            "freshness_score": round(freshness_score, 3),
            "source_trust_score": round(source_trust, 3),
            "content_length_score": round(content_length_score, 3),
            "usefulness_score": round(usefulness, 3),
            "channel_relevance_score": round(relevance, 3),
            "risk_score": round(risk, 3),
            "duplicate_penalty": duplicate_penalty,
            "final_score": round(final, 3),
        }


class TopicCreationService:
    def __init__(self, scoring: TopicScoringService | None = None) -> None:
        self.scoring = scoring or TopicScoringService()

    def create_or_update_topic(self, db: Session, source: Source, item: SourceItem) -> Topic | None:
        if item.duplicate_of_item_id:
            item.extraction_status = "duplicate"
            return None
        channels = source_channels(db, source)
        if item.paywall_or_blocked_detected or item.extraction_status == "blocked":
            status = "blocked_source"
        elif item.extraction_status == "too_short":
            status = "rejected"
        elif item.extraction_status != "extracted":
            status = "rejected"
        else:
            status = "ready_for_dry_run"
        scores = self.scoring.score(source, item, channels)
        existing = db.execute(select(Topic).where(Topic.source_item_id == item.id)).scalar_one_or_none()
        topic = existing or Topic(source_id=source.id, source_item_id=item.id)
        topic.title = item.title or item.canonical_url or item.url
        topic.url = item.canonical_url or item.url
        topic.raw_text = item.extracted_text
        topic.summary = item.extracted_summary or item.summary
        topic.published_at = item.published_at
        topic.detected_at = item.detected_at
        topic.freshness_score = scores["freshness_score"]
        topic.relevance_score = scores["channel_relevance_score"]
        topic.usefulness_score = scores["usefulness_score"]
        topic.originality_score = 0.5 if item.duplicate_of_item_id else 0.82
        topic.importance_score = scores["content_length_score"]
        topic.source_trust_score = scores["source_trust_score"]
        topic.risk_score = scores["risk_score"]
        topic.final_score = scores["final_score"]
        topic.why_this_matters = why_matters(item, channels)
        topic.suggested_angle = suggested_angle(item, channels)
        topic.assigned_channel_ids = [channel.id for channel in channels[:2]]
        topic.is_duplicate = bool(item.duplicate_of_item_id)
        topic.duplicate_of_topic_id = None
        topic.status = "duplicate" if item.duplicate_of_item_id else status
        topic.extraction_status = item.extraction_status
        topic.extraction_error = item.extraction_error
        topic.content_length = item.content_length
        topic.language = item.language
        topic.source_published_at = item.published_at
        topic.canonical_url = item.canonical_url
        topic.paywall_or_blocked_detected = item.paywall_or_blocked_detected
        if existing is None:
            db.add(topic)
            db.flush()
            log_activity(
                db,
                actor_type="system",
                actor_id=None,
                event_type="topic_created_from_source_item",
                entity_type="topic",
                entity_id=topic.id,
                message=f"Topic created from source item: {topic.title}",
                metadata={"source_id": source.id, "source_item_id": item.id, "scores": scores},
            )
        return topic


class SourceFetchService:
    def __init__(self) -> None:
        self.http = HttpFetchService()
        self.extractor = ContentExtractionService()
        self.rss = RssFetchService(self.http, self.extractor)
        self.dedup = DeduplicationService()
        self.topic_creator = TopicCreationService()

    def fetch_source(self, db: Session, source: Source, *, limit: int = 5, create_topics: bool = True) -> IngestionResult:
        result = IngestionResult(source_id=source.id, source_item_ids=[], topic_ids=[])
        if source.status in {"disabled", "paused"}:
            source.health_status = source.status
            source.last_error = f"Source is {source.status}"
            result.last_error = source.last_error
            return result
        if source.type == "ladder_optional":
            source.health_status = "disabled"
            source.last_error = "Ladder optional is disabled by default and must not be used for paywall bypass."
            result.last_error = source.last_error
            log_activity(db, actor_type="system", actor_id=None, event_type="source_fetch_blocked", entity_type="source", entity_id=source.id, message=source.last_error)
            return result

        started = datetime.now(UTC)
        source.last_checked_at = started
        fetched_entries: list[dict[str, Any]] = []
        fetch_error = ""
        duration_ms = 0
        if source.type == "rss":
            fetched_entries, feed_result = self.rss.fetch_items(source, limit=limit)
            fetch_error = feed_result.error
            duration_ms = feed_result.duration_ms
        elif source.type in {"website", "manual_url", "manual", "api_placeholder", "api"}:
            fetch = self.http.fetch(source.url)
            fetch_error = fetch.error
            duration_ms = fetch.duration_ms
            if not fetch.error:
                extracted = self.extractor.extract(fetch.text, fetch.final_url or source.url)
                fetched_entries = [{"url": fetch.final_url or source.url, "extracted": extracted, "raw_html": fetch.text}]
        else:
            fetch_error = f"Unsupported source type: {source.type}"

        if fetch_error:
            source.health_status = "failed"
            source.last_error = fetch_error
            result.failed += 1
            result.last_error = fetch_error
            db.commit()
            return result

        result.fetched_count = len(fetched_entries)
        for entry in fetched_entries:
            extracted: ExtractedContent = entry["extracted"]
            raw_html = entry.get("raw_html", "")
            raw_hash = sha256(raw_html or extracted.text or extracted.summary)
            canonical = extracted.canonical_url or normalize_url(entry["url"])
            duplicate = self.dedup.find_duplicate(db, source, url=normalize_url(entry["url"]), canonical_url=canonical, title=extracted.title, raw_hash=raw_hash)
            if duplicate:
                item = SourceItem(
                    source_id=source.id,
                    url=normalize_url(entry["url"]),
                    canonical_url=canonical,
                    title=extracted.title,
                    summary=extracted.summary,
                    raw_html_hash=raw_hash,
                    extracted_text=extracted.text,
                    extracted_summary=extracted.summary,
                    published_at=extracted.published_at,
                    language=extracted.language or source.language,
                    content_length=len(extracted.text),
                    extraction_status="duplicate",
                    extraction_error="Duplicate source item",
                    paywall_or_blocked_detected=extracted.paywall_or_blocked_detected,
                    duplicate_of_item_id=duplicate.id,
                )
                result.duplicates += 1
            else:
                item = SourceItem(
                    source_id=source.id,
                    url=normalize_url(entry["url"]),
                    canonical_url=canonical,
                    title=extracted.title,
                    summary=extracted.summary,
                    raw_html_hash=raw_hash,
                    extracted_text=extracted.text,
                    extracted_summary=extracted.summary,
                    published_at=extracted.published_at,
                    language=extracted.language or source.language,
                    content_length=len(extracted.text),
                    extraction_status=extracted.status,
                    extraction_error=extracted.error,
                    paywall_or_blocked_detected=extracted.paywall_or_blocked_detected,
                )
                if extracted.status == "extracted":
                    result.extracted_count += 1
                elif extracted.status == "blocked":
                    result.blocked += 1
                elif extracted.status in {"failed", "too_short"}:
                    result.failed += 1
            db.add(item)
            db.flush()
            result.source_item_ids.append(item.id)
            topic = self.topic_creator.create_or_update_topic(db, source, item) if create_topics else None
            if topic:
                result.topic_ids.append(topic.id)
                if topic.status == "ready_for_dry_run":
                    result.topics_created += 1

        source.health_status = "ok" if result.failed == 0 else "warning"
        source.last_error = "" if result.failed == 0 else f"{result.failed} item(s) failed extraction"
        log_activity(
            db,
            actor_type="system",
            actor_id=None,
            event_type="source_fetched",
            entity_type="source",
            entity_id=source.id,
            message=f"Fetched source {source.name}: {result.fetched_count} items, {result.topics_created} topics.",
            metadata={**result.as_dict(), "duration_ms": duration_ms},
        )
        db.commit()
        return result

    def check_health(self, db: Session, source: Source) -> dict[str, Any]:
        started = datetime.now(UTC)
        fetch = self.http.fetch(source.url)
        source.last_checked_at = started
        source.last_error = fetch.error
        source.health_status = "failed" if fetch.error else "ok"
        source.status = "failed" if fetch.error and source.status == "active" else source.status
        metadata = {
            "reachable": not bool(fetch.error),
            "rss_valid": False,
            "last_http_status": fetch.status_code,
            "last_fetch_duration_ms": fetch.duration_ms,
            "last_item_count": 0,
            "last_error": fetch.error,
            "robots_or_paywall_warning": detect_blocked(fetch.text, fetch.text[:5000]) if fetch.text else False,
        }
        if not fetch.error and source.type == "rss":
            parsed = feedparser.parse(fetch.text)
            metadata["rss_valid"] = not bool(parsed.bozo)
            metadata["last_item_count"] = len(parsed.entries)
        log_activity(db, actor_type="system", actor_id=None, event_type="source_health_checked", entity_type="source", entity_id=source.id, message=f"Source health check: {source.name} -> {source.health_status}", metadata=metadata)
        db.commit()
        return metadata


def normalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if not parsed.scheme:
        return url.strip()
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", "", parsed.query, ""))


def normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def strip_tags(value: str) -> str:
    return normalize_text(re.sub(r"<[^>]+>", " ", value or ""))


def summarize_text(text: str, limit: int = 520) -> str:
    text = normalize_text(text)
    if len(text) <= limit:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = ""
    for sentence in sentences:
        if len(summary) + len(sentence) + 1 > limit:
            break
        summary = f"{summary} {sentence}".strip()
    return summary or text[:limit].rsplit(" ", 1)[0]


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except Exception:
            return None


def detect_blocked(html_text: str, text: str) -> bool:
    haystack = f"{html_text[:8000]} {text[:2000]}".lower()
    return any(marker in haystack for marker in BLOCKED_MARKERS)


def detect_language(text: str) -> str:
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cyrillic > latin:
        return "ru"
    if latin:
        return "en"
    return ""


def sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-zа-я0-9 ]+", "", (title or "").lower()).strip()


def title_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    left_words = set(left.split())
    right_words = set(right.split())
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / len(left_words | right_words)


def freshness(published_at: datetime | None) -> float:
    if not published_at:
        return 0.65
    age_hours = max(0.0, (datetime.now(UTC) - published_at).total_seconds() / 3600)
    if age_hours <= 24:
        return 1.0
    if age_hours <= 72:
        return 0.82
    if age_hours <= 24 * 14:
        return 0.58
    return 0.35


def score_usefulness(text: str, title: str) -> float:
    haystack = f"{title} {text}".lower()
    markers = ["how", "why", "guide", "research", "study", "report", "data", "practical", "как", "почему", "исслед", "отчет", "данн", "совет"]
    base = 0.45 + min(0.35, len(text) / 5000)
    return min(1.0, base + 0.04 * sum(marker in haystack for marker in markers))


def score_risk(text: str, channels: list[Channel]) -> float:
    haystack = text.lower()
    markers = ["diagnosis", "treatment", "dosage", "investment advice", "trading", "guaranteed", "война", "лекар", "диагноз", "инвестиц", "гарантир"]
    risk = min(0.75, 0.08 * sum(marker in haystack for marker in markers))
    if any(channel.category in {"health", "money", "news"} for channel in channels):
        risk += 0.05
    return round(min(1.0, risk), 3)


def score_channel_relevance(item: SourceItem, channels: list[Channel]) -> float:
    if not channels:
        return 0.45
    haystack = f"{item.title} {item.summary} {item.extracted_text[:3000]}".lower()
    category_terms = {
        "news": ["report", "announced", "сегодня", "сообщ", "отчет", "нов"],
        "money": ["business", "finance", "cash", "money", "бизнес", "деньг", "финанс"],
        "ai": ["ai", "model", "agent", "automation", "нейрос", "модель", "автоматизац"],
        "health": ["health", "sleep", "nutrition", "сон", "здоров", "питани"],
        "food": ["food", "recipe", "meal", "cook", "еда", "рецепт", "ингредиент"],
    }
    best = 0.4
    for channel in channels:
        terms = category_terms.get(channel.category, [channel.category])
        best = max(best, min(1.0, 0.45 + 0.12 * sum(term in haystack for term in terms)))
    return round(best, 3)


def source_channels(db: Session, source: Source) -> list[Channel]:
    channels = db.execute(
        select(Channel)
        .join(SourceChannelMap, SourceChannelMap.channel_id == Channel.id)
        .where(SourceChannelMap.source_id == source.id, SourceChannelMap.enabled.is_(True), Channel.status == "active")
        .order_by(SourceChannelMap.relevance_weight.desc(), Channel.id)
    ).scalars().all()
    if channels:
        return list(channels)
    return list(db.execute(select(Channel).where(Channel.status == "active").order_by(Channel.id)).scalars().all()[:1])


def why_matters(item: SourceItem, channels: list[Channel]) -> str:
    channel_names = ", ".join(channel.name for channel in channels[:2]) or "ERA"
    return f"Источник даёт материал для {channel_names}: есть публичная ссылка, извлечённый текст и базовая оценка качества источника."


def suggested_angle(item: SourceItem, channels: list[Channel]) -> str:
    category = channels[0].category if channels else "news"
    formulas = {
        "news": "Что произошло, почему это важно и что может быть дальше.",
        "money": "Где здесь деньги, риски и что читатель может проверить сам.",
        "ai": "Что изменилось, как применить и что попробовать сегодня.",
        "health": "Что известно, что не доказано и безопасный практичный вывод.",
        "food": "Идея блюда, ингредиенты, шаги и вариации.",
    }
    return formulas.get(category, "Короткий пересказ с добавленной редакционной ценностью.")
