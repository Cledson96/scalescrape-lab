from __future__ import annotations


DEFAULT_SCHEDULED_SCRAPE_INTERVAL_SECONDS = 6 * 60 * 60
DEFAULT_PROTECTED_TARGET_URL = "http://target-site:4000/protected/items?page=1"
DEFAULT_BOOKS_TO_SCRAPE_URL = "https://books.toscrape.com/catalogue/category/books/science-fiction_16/index.html"


def scheduled_scrape_jobs(
    *,
    interval_seconds: int = DEFAULT_SCHEDULED_SCRAPE_INTERVAL_SECONDS,
    protected_target_url: str = DEFAULT_PROTECTED_TARGET_URL,
    books_to_scrape_url: str = DEFAULT_BOOKS_TO_SCRAPE_URL,
) -> list[dict]:
    return [
        {
            "source": "fake-target",
            "start_url": protected_target_url,
            "mode": "browser",
            "max_pages": 1,
            "interval_seconds": interval_seconds,
        },
        {
            "source": "books-to-scrape",
            "start_url": books_to_scrape_url,
            "mode": "browser",
            "max_pages": 1,
            "interval_seconds": interval_seconds,
        },
    ]
