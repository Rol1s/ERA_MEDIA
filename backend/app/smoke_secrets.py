import os

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.all_models import ActivityEvent, IntegrationSecret
from app.seed import seed_integrations, seed_settings
from app.services.secrets import decrypt_secret, list_secret_status, resolve_secret_value, upsert_secret, disable_secret


FAKE_SECRET = "test-openai-secret-A9f2"


def ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


def main() -> None:
    os.environ["APP_SECRET_KEY"] = os.environ.get("APP_SECRET_KEY") or "smoke-secret-key-for-era"
    seed_settings()
    seed_integrations()
    with SessionLocal() as db:
        existing = db.execute(
            select(IntegrationSecret).where(
                IntegrationSecret.provider == "openai",
                IntegrationSecret.secret_name == "OPENAI_API_KEY",
            )
        ).scalar_one_or_none()
        backup = None
        if existing is not None:
            backup = {
                "integration_id": existing.integration_id,
                "encrypted_value": existing.encrypted_value,
                "masked_value": existing.masked_value,
                "status": existing.status,
                "last_test_at": existing.last_test_at,
                "last_success_at": existing.last_success_at,
                "last_error": existing.last_error,
                "rotated_at": existing.rotated_at,
            }
        row = upsert_secret(db, "openai", "OPENAI_API_KEY", FAKE_SECRET)
        db.add(
            ActivityEvent(
                actor_type="human",
                event_type="secret_updated",
                entity_type="integration_secret",
                entity_id=row.id,
                message="Secret updated: openai/OPENAI_API_KEY",
                metadata_json={"provider": "openai", "secret_name": "OPENAI_API_KEY", "masked_value": row.masked_value},
            )
        )
        db.commit()
        db.refresh(row)

        stored = db.get(IntegrationSecret, row.id)
        ok(stored is not None, "secret row exists")
        ok(stored.encrypted_value != FAKE_SECRET, "encrypted_value differs from plaintext")
        ok(decrypt_secret(stored.encrypted_value) == FAKE_SECRET, "secret decrypts server-side")
        status = list_secret_status(db)
        text = str(status)
        ok(FAKE_SECRET not in text, "status does not return plaintext")
        openai_status = next(item for item in status["providers"] if item["provider"] == "openai")
        ok(openai_status["masked_value"] == "sk-...A9f2", "status returns masked key")

        activity_text = "\n".join(
            str(item.message) + str(item.metadata_json)
            for item in db.execute(select(ActivityEvent).where(ActivityEvent.event_type == "secret_updated")).scalars()
        )
        ok(FAKE_SECRET not in activity_text, "activity_events do not contain plaintext")

        disable_secret(db, "openai", "OPENAI_API_KEY")
        db.commit()
        disabled = list_secret_status(db)
        disabled_openai = next(item for item in disabled["providers"] if item["provider"] == "openai")
        ok(disabled_openai["status"] == "disabled", "delete disables secret")

        os.environ["OPENAI_API_KEY"] = "test-env-fallback-secret-Z9z9"
        resolved = resolve_secret_value(db, "openai", "OPENAI_API_KEY")
        ok(resolved == "test-env-fallback-secret-Z9z9", "env fallback works after delete")

        restored = db.execute(
            select(IntegrationSecret).where(
                IntegrationSecret.provider == "openai",
                IntegrationSecret.secret_name == "OPENAI_API_KEY",
            )
        ).scalar_one_or_none()
        if backup is not None and restored is not None:
            for key, value in backup.items():
                setattr(restored, key, value)
        elif backup is None and restored is not None:
            db.delete(restored)
        db.commit()

    print("SMOKE SECRETS PASSED")


if __name__ == "__main__":
    main()
