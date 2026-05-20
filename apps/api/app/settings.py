from functools import lru_cache
from pydantic import BaseModel
import os


class Settings(BaseModel):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@postgres:5432/scalescrape",
    )
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672//")
    default_source_name: str = "fake-target"
    default_source_url: str = "http://target-site:4000"
    media_root: str = os.getenv("MEDIA_ROOT", "/app/media")


@lru_cache
def get_settings() -> Settings:
    return Settings()

