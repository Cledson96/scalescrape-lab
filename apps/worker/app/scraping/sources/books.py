from __future__ import annotations

from urllib.parse import urljoin

from app.scraping.sources.books_parser import build_books_record_payload, extract_book_external_id, extract_books_category
from app.proxy.manager import ProxyProfileState
from app.scraping.contracts import ScrapedRecord, ScrapeBlocked


BOOKS_TO_SCRAPE_HOST = "books.toscrape.com"


async def scrape_books_to_scrape(
    *,
    page,
    start_url: str,
    max_pages: int,
    proxy: ProxyProfileState,
    gbp_to_brl_rate: float,
    page_timeout_seconds: int,
) -> list[ScrapedRecord]:
    records: list[ScrapedRecord] = []
    current_url: str | None = start_url
    pages_seen = 0
    category = extract_books_category(start_url)
    detail_page = await page.context.new_page()
    detail_page.set_default_timeout(page_timeout_seconds * 1000)

    try:
        while current_url and pages_seen < max_pages:
            response = await page.goto(current_url, wait_until="domcontentloaded")
            status = response.status if response else 0
            if status in (403, 429):
                raise ScrapeBlocked(status, f"bloqueio HTTP {status}")

            cards = page.locator("article.product_pod")
            total = await cards.count()
            if total == 0:
                raise RuntimeError("layout books-to-scrape sem article.product_pod")

            summaries: list[dict[str, str]] = []
            for index in range(total):
                card = cards.nth(index)
                link = card.locator("h3 a")
                title = await link.get_attribute("title") or (await link.inner_text()).strip()
                href = await link.get_attribute("href") or ""
                detail_url = urljoin(current_url, href)
                price_text = (await card.locator(".price_color").inner_text()).strip()
                rating_class = await card.locator(".star-rating").get_attribute("class") or ""
                availability = (await card.locator(".availability").inner_text()).strip()
                summaries.append(
                    {
                        "title": title,
                        "detail_url": detail_url,
                        "price_text": price_text,
                        "rating_class": rating_class,
                        "availability": availability,
                    }
                )

            next_link = page.locator("li.next a")
            next_url = None
            if await next_link.count():
                href = await next_link.first.get_attribute("href")
                next_url = urljoin(current_url, href or "")

            for summary in summaries:
                detail_response = await detail_page.goto(summary["detail_url"], wait_until="domcontentloaded")
                detail_status = detail_response.status if detail_response else 0
                if detail_status in (403, 429):
                    raise ScrapeBlocked(detail_status, f"bloqueio HTTP {detail_status} no detalhe do livro")
                description = await read_book_description(detail_page)
                payload = build_books_record_payload(
                    title=summary["title"],
                    category=category,
                    detail_url=summary["detail_url"],
                    price_text=summary["price_text"],
                    rating_class=summary["rating_class"],
                    description=description,
                    availability=summary["availability"],
                    gbp_to_brl_rate=gbp_to_brl_rate,
                )
                records.append(
                    ScrapedRecord(
                        external_id=extract_book_external_id(summary["detail_url"]),
                        title=summary["title"],
                        detail_url=summary["detail_url"],
                        raw_data={**payload, "proxy": proxy.name},
                    )
                )

            current_url = next_url
            pages_seen += 1
    finally:
        await detail_page.close()

    return records


async def read_book_description(page) -> str:
    description = page.locator("#product_description + p")
    if await description.count() == 0:
        return ""
    return (await description.inner_text()).strip()
