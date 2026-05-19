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
    target_site_username: str = os.getenv("TARGET_SITE_USERNAME", "demo")
    target_site_password: str = os.getenv("TARGET_SITE_PASSWORD", "demo123")
    enable_proxy_rotation: bool = os.getenv("ENABLE_PROXY_ROTATION", "true").lower() == "true"
    allowed_proxy_target_hosts: set[str] = None  # type: ignore[assignment]
    scraper_max_attempts: int = int(os.getenv("SCRAPER_MAX_ATTEMPTS", "3"))
    scraper_page_timeout_seconds: int = int(os.getenv("SCRAPER_PAGE_TIMEOUT_SECONDS", "30"))
    scraper_job_timeout_seconds: int = int(os.getenv("SCRAPER_JOB_TIMEOUT_SECONDS", "180"))
    gbp_to_brl_rate: float = float(os.getenv("GBP_TO_BRL_RATE", "6.50"))
    media_root: str = os.getenv("MEDIA_ROOT", "/app/media")
    globo_max_articles: int = int(os.getenv("GLOBO_MAX_ARTICLES", "12"))
    enable_scheduled_scraping: bool = os.getenv("ENABLE_SCHEDULED_SCRAPING", "true").lower() == "true"
    scheduled_scrape_interval_seconds: int = int(os.getenv("SCHEDULED_SCRAPE_INTERVAL_SECONDS", "21600"))
    scheduled_protected_target_url: str = os.getenv(
        "SCHEDULED_PROTECTED_TARGET_URL",
        "http://target-site:4000/protected/items?page=1",
    )
    scheduled_books_to_scrape_url: str = os.getenv(
        "SCHEDULED_BOOKS_TO_SCRAPE_URL",
        "https://books.toscrape.com/catalogue/category/books/science-fiction_16/index.html",
    )
    scheduled_globo_home_url: str = os.getenv("SCHEDULED_GLOBO_HOME_URL", "https://www.globo.com/")
    scheduled_betano_football_url: str = os.getenv(
        "SCHEDULED_BETANO_FOOTBALL_URL",
        "https://www.betano.bet.br/sport/futebol/",
    )
    betano_max_leagues: int = int(os.getenv("BETANO_MAX_LEAGUES", "10"))
    betano_proxy_url: str = os.getenv("BETANO_PROXY_URL", "")

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_captcha_hosts",
            csv_env("ALLOWED_CAPTCHA_HOSTS", "target-site,localhost,127.0.0.1"),
        )
        object.__setattr__(
            self,
            "allowed_proxy_target_hosts",
            csv_env("ALLOWED_PROXY_TARGET_HOSTS", "target-site,localhost,127.0.0.1")
            | {"books.toscrape.com", "www.globo.com", "www.betano.bet.br"},
        )


settings = Settings()

