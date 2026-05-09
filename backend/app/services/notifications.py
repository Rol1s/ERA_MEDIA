from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.all_models import Notification
from app.services.org import log_activity
from app.services.settings import get_settings


def create_notification(
    db: Session,
    *,
    severity: str,
    title: str,
    message: str,
    entity_type: str = "",
    entity_id: int | None = None,
) -> Notification:
    notification = Notification(
        severity=severity,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        status="unread",
        created_at=datetime.now(UTC),
    )
    db.add(notification)
    db.flush()
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="notification_created",
        entity_type="notification",
        entity_id=notification.id,
        message=f"Notification: {title}",
        metadata={"severity": severity, "related_entity_type": entity_type, "related_entity_id": entity_id},
    )
    return notification


class NotificationDispatcher:
    def send(self, db: Session, notification: Notification) -> dict[str, Any]:
        raise NotImplementedError


class MockNotificationDispatcher(NotificationDispatcher):
    def send(self, db: Session, notification: Notification) -> dict[str, Any]:
        log_activity(
            db,
            actor_type="system",
            actor_id=None,
            event_type="notification_dispatch_mock",
            entity_type="notification",
            entity_id=notification.id,
            message=f"Mock notification dispatch: {notification.title}",
        )
        return {"status": "mock_logged"}


class MaxNotificationDispatcher(NotificationDispatcher):
    def send(self, db: Session, notification: Notification) -> dict[str, Any]:
        log_activity(
            db,
            actor_type="system",
            actor_id=None,
            event_type="notification_dispatch_dry_run",
            entity_type="notification",
            entity_id=notification.id,
            message="MAX admin notification dispatcher is prepared but public publishing is disabled.",
        )
        return {"status": "dry_run_only"}


class WebhookNotificationDispatcher(NotificationDispatcher):
    def send(self, db: Session, notification: Notification) -> dict[str, Any]:
        log_activity(
            db,
            actor_type="system",
            actor_id=None,
            event_type="notification_dispatch_dry_run",
            entity_type="notification",
            entity_id=notification.id,
            message="Webhook notification dispatcher skeleton was called in dry-run mode.",
        )
        return {"status": "dry_run_only"}


def dispatcher_for_settings(db: Session) -> NotificationDispatcher:
    settings = get_settings(db)
    provider = settings.get("admin_notification_provider", "none")
    if provider == "max":
        return MaxNotificationDispatcher()
    if provider == "webhook":
        return WebhookNotificationDispatcher()
    return MockNotificationDispatcher()


def dispatch_notification(db: Session, notification: Notification) -> dict[str, Any]:
    return dispatcher_for_settings(db).send(db, notification)
