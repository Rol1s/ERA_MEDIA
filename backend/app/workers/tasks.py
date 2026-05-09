from app.agents.orchestrator import generate_draft_for_topic
from app.db.session import SessionLocal
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.generate_draft_task")
def generate_draft_task(topic_id: int, channel_id: int | None = None) -> int:
    with SessionLocal() as db:
        post = generate_draft_for_topic(db, topic_id=topic_id, channel_id=channel_id)
        return post.id


@celery_app.task(name="app.workers.tasks.scheduler_placeholder")
def scheduler_placeholder() -> str:
    return "Scheduler placeholder: source collection jobs can be registered here."

