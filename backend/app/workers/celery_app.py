from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "era_media_factory",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.task_routes = {"app.workers.tasks.*": {"queue": "era"}}
celery_app.conf.beat_schedule = {
    "scheduler-placeholder-every-hour": {
        "task": "app.workers.tasks.scheduler_placeholder",
        "schedule": 3600.0,
    }
}

