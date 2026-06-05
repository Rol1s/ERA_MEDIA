from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.all_models import Channel, Post
from app.services import media_producer


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with SessionLocal() as db:
        channel = db.execute(select(Channel).order_by(Channel.id)).scalars().first()
        assert_true(channel is not None, "channel missing")
        post = Post(
            channel_id=channel.id,
            title="Smoke media post",
            body="Тестовый русский текст для проверки Media Producer.",
            source_urls=["https://example.org/story"],
            generation_mode="dry_run",
            provider="openai",
            model="gpt-5.5",
            status="needs_review",
            risk_score=0.2,
        )
        db.add(post)
        db.flush()

        media_producer._fetch_text = lambda url: '<html><head><meta property="og:image" content="https://example.org/image.jpg"></head></html>'  # type: ignore[method-assign]
        media_producer._download_image = lambda url, post_id: f"/media/source-post-{post_id}-smoke.jpg"  # type: ignore[method-assign]
        media_producer.prepare_media_for_post(db, post, generate_fallback=False)
        assert_true(post.media_source_type == "source_preview", "preview was not used")
        assert_true(post.media_status == "found", "media status should be found")
        assert_true((post.structured_outputs_json or {}).get("rich_media", {}).get("media_first") is True, "rich media plan missing")
        post.status = "archived"

        risky = Post(
            channel_id=channel.id,
            title="Удар дронов по городу",
            body="Проверяем, что высокорисковая новость без реального фото не получает fake event image.",
            source_urls=["https://example.org/war-story"],
            generation_mode="dry_run",
            provider="openai",
            model="gpt-5.5",
            status="needs_review",
            risk_score=80,
        )
        db.add(risky)
        db.flush()
        media_producer._fetch_text = lambda url: "<html><head></head><body>No preview</body></html>"  # type: ignore[method-assign]
        media_producer.prepare_media_for_post(db, risky, generate_fallback=True)
        assert_true(risky.media_status == "needs_review", "high-risk media should require review")
        assert_true(risky.media_source_type == "none", "high-risk media should not be generated without source preview")
        assert_true(risky.image_generation_status == "source_media_required", "high-risk media blocker missing")
        risky.status = "archived"
        db.commit()
    print("smoke-media-producer: passed")


if __name__ == "__main__":
    main()
