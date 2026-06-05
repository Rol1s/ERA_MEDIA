from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models.all_models import Channel, Post, Source, SourceChannelMap, SourceItem, Topic
from app.services import media_producer
from app.services.max_packaging import prepare_max_package
from app.services.source_ingestion import FetchResult, SourceFetchService
from app.services.zero_token_guard import assert_zero_token_delta, zero_token_delta, zero_token_snapshot


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeHttpFetch:
    def __init__(self, feed_url: str, article_url: str) -> None:
        self.feed_url = feed_url
        self.article_url = article_url

    def fetch(self, url: str, *, timeout_seconds: int = 12) -> FetchResult:
        if url == self.feed_url:
            text = f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Zero Token Smoke Feed</title>
    <item>
      <title>Zero-token intake smoke story</title>
      <link>{self.article_url}</link>
      <pubDate>Wed, 13 May 2026 07:00:00 GMT</pubDate>
      <description>Public summary for a smoke test story with enough context to create a source item.</description>
    </item>
  </channel>
</rss>"""
            return FetchResult(url=url, final_url=url, status_code=200, content_type="application/rss+xml", text=text, duration_ms=1)

        paragraph = (
            "This public article explains a local civic update, names the public source, "
            "states what happened, why it matters, who is affected, and what remains uncertain. "
            "The text is intentionally long enough for extraction, but it is deterministic and does not require an LLM. "
        )
        body = paragraph * 8
        html = f"""<html lang="en">
<head>
  <title>Zero-token intake smoke story</title>
  <meta property="og:title" content="Zero-token intake smoke story">
  <meta property="og:description" content="A deterministic article for intake testing.">
  <meta property="article:published_time" content="2026-05-13T07:00:00+00:00">
</head>
<body><article><h1>Zero-token intake smoke story</h1><p>{body}</p></article></body>
</html>"""
        return FetchResult(url=url, final_url=self.article_url, status_code=200, content_type="text/html", text=html, duration_ms=1)


def ensure_channel(db) -> Channel:
    channel = db.execute(select(Channel).where(Channel.slug == "smoke-zero-token")).scalar_one_or_none()
    if channel is None:
        channel = Channel(
            name="Smoke Zero Token",
            slug="smoke-zero-token",
            category="news",
            description="Smoke-only channel.",
            status="active",
        )
        db.add(channel)
        db.flush()
    return channel


def ensure_source(db, channel: Channel, feed_url: str) -> Source:
    source = db.execute(select(Source).where(Source.name == "Smoke Zero Token Source")).scalar_one_or_none()
    if source is None:
        source = Source(
            name="Smoke Zero Token Source",
            url=feed_url,
            type="rss",
            language="en",
            status="active",
            trust_score=0.9,
            source_priority="high",
            ingestion_enabled=True,
            is_demo=True,
        )
        db.add(source)
        db.flush()
    source.url = feed_url
    source.type = "rss"
    source.status = "active"
    source.ingestion_enabled = True
    source.is_demo = True
    mapping = db.execute(
        select(SourceChannelMap).where(SourceChannelMap.source_id == source.id, SourceChannelMap.channel_id == channel.id)
    ).scalar_one_or_none()
    if mapping is None:
        db.add(SourceChannelMap(source_id=source.id, channel_id=channel.id, relevance_weight=1.0, enabled=True))
    db.commit()
    db.refresh(source)
    return source


def main() -> None:
    with SessionLocal() as db:
        seed = int(datetime.now(UTC).timestamp())
        feed_url = f"https://example.org/zero-token-{seed}.rss"
        article_url = f"https://example.org/zero-token-{seed}/story"
        channel = ensure_channel(db)
        source = ensure_source(db, channel, feed_url)

        before = zero_token_snapshot(db)

        service = SourceFetchService()
        fake_http = FakeHttpFetch(feed_url, article_url)
        service.http = fake_http  # type: ignore[assignment]
        service.rss.http = fake_http  # type: ignore[assignment]

        first = service.fetch_source(db, source, limit=1, create_topics=True)
        assert_true(first.fetched_count == 1, "source fetch created one item")
        assert_true(bool(first.source_item_ids), "source fetch stored source item")
        assert_true(first.as_dict()["llm_calls"] == 0, "source fetch reports zero LLM calls")

        second = service.fetch_source(db, source, limit=1, create_topics=True)
        assert_true(second.duplicates >= 1, "dedupe detects repeated item")
        assert_true(second.topics_created == 0, "dedupe prevents duplicate topic")

        post = Post(
            channel_id=channel.id,
            topic_id=first.topic_ids[0] if first.topic_ids else None,
            title="Zero-token MAX package",
            body="Короткий русский текст для проверки упаковки без вызова модели.",
            source_urls=[article_url, feed_url],
            generation_mode="production_manual",
            provider="openai",
            model="no-call",
            status="needs_review",
            risk_score=0.1,
        )
        db.add(post)
        db.flush()
        prepare_max_package(db, post)
        assert_true(".rss" not in post.max_packaged_text, "feed URL hidden from MAX package")

        media_producer._fetch_text = lambda url: '<html><head><meta property="og:image" content="https://example.org/preview.jpg"></head></html>'  # type: ignore[method-assign]
        media_producer._download_image = lambda url, post_id: f"/media/source-post-{post_id}-zero-token.jpg"  # type: ignore[method-assign]
        media_producer.prepare_media_for_post(db, post, generate_fallback=False)
        assert_true(post.media_source_type == "source_preview", "media preview found without image generation")
        assert_true(post.media_status == "found", "media preview status is found")

        after = zero_token_snapshot(db)
        assert_zero_token_delta(before, after, step="zero-token intake")
        delta = zero_token_delta(before, after)

        topic_ids = set(first.topic_ids or []) | set(second.topic_ids or [])
        topic_ids.update(
            db.execute(select(Topic.id).where(Topic.source_id == source.id)).scalars().all()
        )
        item_ids = set(first.source_item_ids or []) | set(second.source_item_ids or [])
        item_ids.update(
            db.execute(select(SourceItem.id).where(SourceItem.source_id == source.id)).scalars().all()
        )
        db.delete(post)
        db.flush()
        for topic_id in topic_ids:
            topic = db.get(Topic, topic_id)
            if topic:
                db.delete(topic)
        if item_ids:
            db.execute(
                update(SourceItem)
                .where(SourceItem.duplicate_of_item_id.in_(list(item_ids)))
                .values(duplicate_of_item_id=None)
            )
        for item_id in item_ids:
            item = db.get(SourceItem, item_id)
            if item:
                db.delete(item)
        mapping = db.execute(
            select(SourceChannelMap).where(SourceChannelMap.source_id == source.id, SourceChannelMap.channel_id == channel.id)
        ).scalar_one_or_none()
        if mapping:
            db.delete(mapping)
        db.delete(source)
        db.delete(channel)
        db.commit()

        Path("docs").mkdir(exist_ok=True)
        Path("docs/ZERO_TOKEN_INTAKE_REPORT.md").write_text(
            "\n".join(
                [
                    "# Zero Token Intake Report",
                    "",
                    "## Verified zero-token steps",
                    "",
                    "- RSS/source fetch",
                    "- article extraction",
                    "- deduplication",
                    "- source item and topic scoring",
                    "- MAX package formatting",
                    "- source preview media lookup when `generate_fallback=false`",
                    "",
                    "## Verification result",
                    "",
                    f"- agent_runs delta: {delta['agent_runs']}",
                    f"- cost_events delta: {delta['cost_events']}",
                    f"- input tokens delta: {delta['tokens_input']}",
                    f"- output tokens delta: {delta['tokens_output']}",
                    f"- estimated cost delta: {delta['estimated_cost']}",
                    "",
                    "## Still not zero-token",
                    "",
                    "- draft writing / translation / rewrite",
                    "- senior agenda LLM pass",
                    "- editorial quality loop when it uses an LLM",
                    "- generated visuals",
                    "",
                    "Relay channels must label source scanning as zero-token, but Russian rewrite remains a paid LLM step unless replaced by templates or a local model.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print("smoke-zero-token-intake: passed")


if __name__ == "__main__":
    main()
