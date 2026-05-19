from __future__ import annotations

from urllib.parse import urljoin

from app.captcha.base import CaptchaResolverProvider
from app.login_captcha import handle_login_if_present, solve_local_challenge
from app.proxy.manager import ProxyProfileState
from app.scraper_contracts import LoginCredentials, ScrapedRecord, ScrapeBlocked


async def scrape_target_site(
    *,
    page,
    start_url: str,
    max_pages: int,
    proxy: ProxyProfileState,
    captcha_provider: CaptchaResolverProvider,
    login_credentials: LoginCredentials,
) -> list[ScrapedRecord]:
    records: list[ScrapedRecord] = []
    current_url: str | None = start_url
    pages_seen = 0

    while current_url and pages_seen < max_pages:
        response = await page.goto(current_url, wait_until="domcontentloaded")
        status = response.status if response else 0
        if status in (403, 429):
            raise ScrapeBlocked(status, f"bloqueio HTTP {status}")

        if await handle_login_if_present(page, current_url, captcha_provider, login_credentials):
            response = await page.goto(current_url, wait_until="domcontentloaded")
            status = response.status if response else 0
            if status in (403, 429):
                raise ScrapeBlocked(status, f"bloqueio HTTP {status} apos login")

        if await page.locator("#captcha-challenge").count():
            await solve_local_challenge(page, start_url, captcha_provider, proxy)
            response = await page.goto(current_url, wait_until="domcontentloaded")
            status = response.status if response else 0
            if status in (403, 429):
                raise ScrapeBlocked(status, f"bloqueio HTTP {status} apos captcha")

        cards = page.locator(".item-card")
        total = await cards.count()
        if total == 0:
            raise RuntimeError("layout sem .item-card")

        for index in range(total):
            card = cards.nth(index)
            external_id = await card.get_attribute("data-item-id") or ""
            title = await card.locator(".item-title").inner_text()
            href = await card.locator(".detail-link").get_attribute("href") or ""
            records.append(
                ScrapedRecord(
                    external_id=external_id,
                    title=title.strip(),
                    detail_url=urljoin(current_url, href),
                    raw_data={"proxy": proxy.name, "source": current_url},
                )
            )

        next_link = page.locator(".next-page")
        if await next_link.count():
            href = await next_link.first.get_attribute("href")
            current_url = urljoin(current_url, href or "")
        else:
            current_url = None
        pages_seen += 1

    return records
