from dataclasses import dataclass
import os


def csv_env(name: str, default: str) -> set[str]:
    return {item.strip() for item in os.getenv(name, default).split(",") if item.strip()}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@postgres:5432/scalescrape",
    )
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672//")
    enable_real_2captcha: bool = os.getenv("ENABLE_REAL_2CAPTCHA", "false").lower() == "true"
    two_captcha_api_key: str = os.getenv("TWO_CAPTCHA_API_KEY", "")
    allowed_captcha_hosts: set[str] = None  # type: ignore[assignment]
    max_captcha_solves_per_run: int = int(os.getenv("MAX_CAPTCHA_SOLVES_PER_RUN", "20"))
    enable_proxy_rotation: bool = os.getenv("ENABLE_PROXY_ROTATION", "true").lower() == "true"
    allowed_proxy_target_hosts: set[str] = None  # type: ignore[assignment]
    scraper_max_attempts: int = int(os.getenv("SCRAPER_MAX_ATTEMPTS", "3"))
    scraper_page_timeout_seconds: int = int(os.getenv("SCRAPER_PAGE_TIMEOUT_SECONDS", "30"))
    scraper_job_timeout_seconds: int = int(os.getenv("SCRAPER_JOB_TIMEOUT_SECONDS", "180"))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_captcha_hosts",
            csv_env("ALLOWED_CAPTCHA_HOSTS", "target-site,localhost,127.0.0.1"),
        )
        object.__setattr__(
            self,
            "allowed_proxy_target_hosts",
            csv_env("ALLOWED_PROXY_TARGET_HOSTS", "target-site,localhost,127.0.0.1"),
        )


settings = Settings()

