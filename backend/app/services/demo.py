from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_topic_pipeline
from app.models.all_models import Channel, Source, SourceChannelMap, Topic


def create_demo_data(db: Session) -> dict[str, int]:
    channel = db.execute(select(Channel).where(Channel.slug == "era-ai")).scalar_one_or_none()
    if channel is None:
        channel = db.execute(select(Channel).where(Channel.status == "active").order_by(Channel.id)).scalar_one()

    source = db.execute(select(Source).where(Source.name == "ERA Demo Source")).scalar_one_or_none()
    if source is None:
        source = Source(
            name="ERA Demo Source",
            url="https://example.com/era-demo-source",
            type="manual",
            language="en",
            trust_score=0.85,
            status="active",
            requires_review=True,
            health_status="ok",
            is_demo=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

    mapping = db.execute(
        select(SourceChannelMap).where(
            SourceChannelMap.source_id == source.id,
            SourceChannelMap.channel_id == channel.id,
        )
    ).scalar_one_or_none()
    if mapping is None:
        db.add(SourceChannelMap(source_id=source.id, channel_id=channel.id, relevance_weight=1.0, enabled=True))
        db.commit()

    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    topic = Topic(
        source_id=source.id,
        title=f"Demo: AI agents help small teams coordinate content ({stamp})",
        url="https://example.com/era-demo-ai-agents",
        summary="A safe demo topic showing how bounded AI agents can research, factcheck, draft and route content.",
        raw_text=(
            "AI agents can help small editorial teams discover topics, collect sources, run checks, "
            "draft useful posts and keep humans in the review loop."
        ),
        status="new",
        source_trust_score=source.trust_score,
        usefulness_score=0.82,
        originality_score=0.74,
        relevance_score=0.88,
        final_score=0.81,
        why_this_matters="Показывает, как безопасно запускать редакционную фабрику без бесконечных циклов.",
        suggested_angle="Объяснить, как маленькая команда может использовать агентов, сохраняя контроль человека.",
        assigned_channel_ids=[channel.id],
        is_demo=True,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)

    post = run_topic_pipeline(db, topic_id=topic.id, channel_id=channel.id, manual_override=True)
    if post.status != "needs_review":
        post.status = "needs_review"
    post.is_demo = True
    db.commit()
    db.refresh(post)

    return {"source_id": source.id, "topic_id": topic.id, "post_id": post.id}
