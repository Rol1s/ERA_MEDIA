from __future__ import annotations

from sqlalchemy import select

from app.api.routes.owner_bot import _create_public_submission
from app.db.session import SessionLocal
from app.models.all_models import NewsroomSubmission


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    update = {
        "message": {
            "chat": {"id": 123456},
            "from": {"first_name": "Reader"},
            "text": "Проверьте новость: https://example.org/story",
        }
    }
    with SessionLocal() as db:
        submission_id = _create_public_submission(db, update, "123456")
        item = db.execute(select(NewsroomSubmission).where(NewsroomSubmission.id == submission_id)).scalar_one()
        assert_true(item.status == "new", "submission status is not new")
        assert_true("Проверьте" in item.text, "submission text missing")
        item.status = "rejected"
        item.rejected_reason = "smoke cleanup"
        db.commit()
    print("smoke-owner-bot: passed")


if __name__ == "__main__":
    main()
