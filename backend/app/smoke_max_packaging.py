from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.all_models import Channel, PlatformChannel, Post
from app.services.max_packaging import prepare_max_package


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with SessionLocal() as db:
        channel = db.execute(select(Channel).where(Channel.slug == "smoke-max-packaging")).scalar_one_or_none()
        if channel is None:
            channel = Channel(
                name="Smoke MAX Packaging",
                slug="smoke-max-packaging",
                category="news",
                description="Smoke-only channel.",
                status="active",
            )
            db.add(channel)
            db.flush()
        platform = db.execute(select(PlatformChannel).where(PlatformChannel.channel_id == channel.id, PlatformChannel.platform == "max")).scalar_one_or_none()
        if platform is None:
            platform = PlatformChannel(
                channel_id=channel.id,
                platform="max",
                external_chat_id="smoke-chat",
                external_channel_url="https://max.ru/smoke-channel",
                status="connected",
                can_publish=True,
            )
            db.add(platform)
            db.flush()
        else:
            platform.external_channel_url = "https://max.ru/smoke-channel"
        post = Post(
            channel_id=channel.id,
            title="Тест MAX упаковки",
            body=(
                "Что произошло\n\n"
                "Это русский короткий пост о решении компании и его последствиях для рынка.\n\n"
                "Деньги — в узких местах цепочки поставок.\n\n"
                "Какие риски? Главный риск — циклическая зависимость.\n\n"
                "Кому полезно знать? Поставщикам оборудования.\n\n"
                "**Что это значит для рынка:**\n\n"
                "1. **Повышение планки зарплат:** Этот пункт не должен стать отдельной рубрикой в MAX.\n\n"
                "**Для малого и среднего бизнеса:**\n\n"
                "**Вывод:**\n\n"
                "Факт отдельно от оценки."
            ),
            source_urls=["https://example.org/story", "https://example.org/rss.xml"],
            generation_mode="dry_run",
            provider="openai",
            model="gpt-5.5",
            status="approved",
        )
        db.add(post)
        db.flush()
        prepare_max_package(db, post)
        assert_true("Что произошло" not in post.max_packaged_text, "template phrase leaked")
        assert_true("Деньги —" not in post.max_packaged_text, "money brief heading leaked")
        assert_true("Какие риски" not in post.max_packaged_text, "risk brief heading leaked")
        assert_true("Кому полезно знать" not in post.max_packaged_text, "useful-for brief heading leaked")
        assert_true("Что это значит для рынка" not in post.max_packaged_text, "market meaning heading leaked")
        assert_true("Для малого и среднего бизнеса" not in post.max_packaged_text, "smb heading leaked")
        assert_true("Вывод:" not in post.max_packaged_text, "conclusion heading leaked")
        assert_true("Повышение планки зарплат" not in post.max_packaged_text, "numbered brief subheading leaked")
        assert_true("**" not in post.max_packaged_text.replace("**Тест MAX упаковки**", ""), "body markdown leaked")
        assert_true(".xml" not in post.max_packaged_text, "rss/xml leaked")
        assert_true("Источник:" in post.max_packaged_text, "source missing")
        assert_true(isinstance(post.max_buttons_json, dict), "buttons json missing")
        assert_true("Подписаться на канал: https://max.ru/smoke-channel" in post.max_packaged_text, "subscribe link missing")
        assert_true(any(button.get("url") == "https://max.ru/smoke-channel" for button in post.max_buttons_json.get("buttons", [])), "subscribe button missing")
        db.delete(post)
        db.flush()
        db.delete(platform)
        db.flush()
        db.delete(channel)
        db.commit()
    print("smoke-max-packaging: passed")


if __name__ == "__main__":
    main()
