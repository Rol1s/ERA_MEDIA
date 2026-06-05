from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_redis_url() -> str:
    return ""


class Settings(BaseSettings):
    app_name: str = "ERA Media Factory"
    database_url: str = "postgresql+psycopg://era:era@localhost:5432/era_media"
    redis_url: str = Field(default_factory=_default_redis_url)
    celery_broker_url: str = Field(default_factory=_default_redis_url)
    celery_result_backend: str = Field(default_factory=_default_redis_url)
    backend_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:13000,http://127.0.0.1:13000"
    admin_username: str = "admin"
    admin_password: str = ""
    dev_mode: bool = True
    app_secret_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
