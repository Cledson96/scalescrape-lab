from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from urllib.parse import urljoin
import asyncio

from app.books import (
    build_books_record_payload,
    extract_book_external_id,
    extract_books_category,
)
from app.captcha.base import CaptchaResolverProvider
from app.globo import (
    build_globo_record_payload,
    extract_globo_external_id,
    globo_image_paths,
    is_allowed_globo_image_url,
    parse_globo_article_detail,
    parse_globo_home_cards,
)
from app.metrics import CAPTCHA_DETECTED, CAPTCHA_SOLVE_DURATION, CAPTCHA_SOLVED
from app.policy import host_from_url
from app.proxy.manager import ProxyProfileState


BOOKS_TO_SCRAPE_HOST = "books.toscrape.com"
GLOBO_HOME_HOST = "www.globo.com"


@dataclass
class ScrapedRecord:
    external_id: str
    title: str
    detail_url: str
    raw_data: dict


@dataclass(frozen=True)
class LoginCredentials:
    username: str
    password: str


class ScrapeBlocked(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


async def scrape_with_playwright(
    *,
    start_url: str,
    max_pages: int,
    proxy: ProxyProfileState,
    captcha_provider: CaptchaResolverProvider,
    login_credentials: LoginCredentials,
    page_timeout_seconds: int,
    gbp_to_brl_rate: float = 6.5,
    media_root: str = "/app/media",
    globo_max_articles: int = 12,
) -> list[ScrapedRecord]:
    from playwright.async_api import async_playwright

    records: list[ScrapedRecord] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            extra_http_headers={"X-Lab-Proxy-Id": proxy.name},
            user_agent="ScaleScrapeLab/1.0",
        )
        page = await context.new_page()
        page.set_default_timeout(page_timeout_seconds * 1000)
        if host_from_url(start_url) == BOOKS_TO_SCRAPE_HOST:
            records = await scrape_books_to_scrape(
                page=page,
                start_url=start_url,
                max_pages=max_pages,
                proxy=proxy,
                gbp_to_brl_rate=gbp_to_brl_rate,
                page_timeout_seconds=page_timeout_seconds,
            )
            await browser.close()
            return records

        if host_from_url(start_url) == GLOBO_HOME_HOST:
            records = await scrape_globo_home(
                page=page,
                start_url=start_url,
                max_pages=max_pages,
                proxy=proxy,
                page_timeout_seconds=page_timeout_seconds,
                media_root=media_root,
                max_articles=globo_max_articles,
            )
            await browser.close()
            return records

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

        await browser.close()
    return records


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


async def scrape_globo_home(
    *,
    page,
    start_url: str,
    max_pages: int,
    proxy: ProxyProfileState,
    page_timeout_seconds: int,
    media_root: str,
    max_articles: int,
) -> list[ScrapedRecord]:
    response = await page.goto(start_url, wait_until="domcontentloaded")
    status = response.status if response else 0
    if status in (403, 429):
        raise ScrapeBlocked(status, f"bloqueio HTTP {status}")

    html = await page.content()
    cards = parse_globo_home_cards(html, base_url=start_url, max_articles=max_articles * max_pages)
    if not cards:
        raise RuntimeError("layout globo sem links .post__link")

    detail_page = await page.context.new_page()
    detail_page.set_default_timeout(page_timeout_seconds * 1000)
    records: list[ScrapedRecord] = []
    try:
        for card in cards[:max_articles]:
            detail_url = card["detail_url"]
            detail = {"title": card["title"], "description": "", "image_url": card["image_url"]}
            detail_response = await detail_page.goto(detail_url, wait_until="domcontentloaded")
            detail_status = detail_response.status if detail_response else 0
            if detail_status in (403, 429):
                raise ScrapeBlocked(detail_status, f"bloqueio HTTP {detail_status} no detalhe Globo")
            if 200 <= detail_status < 400:
                detail = {**detail, **parse_globo_article_detail(await detail_page.content())}

            title = detail["title"] or card["title"]
            image_original_url = detail["image_url"] or card["image_url"]
            external_id = extract_globo_external_id(detail_url)
            image_path = ""
            image_public_path = ""
            if is_allowed_globo_image_url(image_original_url):
                image_path, image_public_path = await download_globo_image(
                    page=detail_page,
                    image_url=image_original_url,
                    external_id=external_id,
                    media_root=media_root,
                )

            payload = build_globo_record_payload(
                title=title,
                category=card["category"],
                detail_url=detail_url,
                description=detail["description"],
                image_original_url=image_original_url,
                image_path=image_path,
                image_public_path=image_public_path,
            )
            records.append(
                ScrapedRecord(
                    external_id=external_id,
                    title=title,
                    detail_url=detail_url,
                    raw_data={**payload, "proxy": proxy.name},
                )
            )
    finally:
        await detail_page.close()

    return records


async def download_globo_image(*, page, image_url: str, external_id: str, media_root: str) -> tuple[str, str]:
    if not is_allowed_globo_image_url(image_url):
        return "", ""

    response = await page.context.request.get(
        image_url,
        headers={"user-agent": "ScaleScrapeLab/1.0"},
        timeout=15000,
    )
    if not response.ok:
        return "", ""

    image_path, image_public_path = globo_image_paths(
        media_root=media_root,
        external_id=external_id,
        image_url=image_url,
    )
    target = Path(image_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(await response.body())
    return image_path, image_public_path


async def handle_login_if_present(
    page,
    start_url: str,
    provider: CaptchaResolverProvider,
    credentials: LoginCredentials,
) -> bool:
    login_form = page.locator("#login-form")
    if await login_form.count() == 0:
        return False

    CAPTCHA_DETECTED.inc()

    recaptcha_widget = page.locator(".g-recaptcha")
    has_recaptcha = await recaptcha_widget.count() > 0

    if has_recaptcha:
        sitekey = await recaptcha_widget.first.get_attribute("data-sitekey")
        if not sitekey:
            raise RuntimeError("reCAPTCHA widget sem data-sitekey")
        source_host = host_from_url(start_url)
        page_url = page.url
        # 2Captcha API requires a valid public-looking domain/TLD to accept the task.
        # We swap local docker hosts to the user's real public domain which is 
        # registered in their Google reCAPTCHA allowed domains.
        safe_page_url = page_url.replace("http://target-site:", "http://scalescrape.cledson.com.br:")
        
        start = monotonic()
        token = await asyncio.to_thread(provider.solve_recaptcha, sitekey, safe_page_url, source_host)
        CAPTCHA_SOLVE_DURATION.observe(monotonic() - start)
        CAPTCHA_SOLVED.inc()

        # Inject the reCAPTCHA response token into the form
        await page.evaluate(
            """(token) => {
                let textarea = document.getElementById('g-recaptcha-response');
                if (!textarea) {
                    textarea = document.createElement('textarea');
                    textarea.id = 'g-recaptcha-response';
                    textarea.name = 'g-recaptcha-response';
                    textarea.style.display = 'none';
                    document.getElementById('login-form').appendChild(textarea);
                }
                textarea.value = token;
            }""",
            token,
        )
    else:
        # Fallback: local image captcha (challenge page)
        challenge = page.locator("#captcha-challenge")
        challenge_id = await challenge.get_attribute("data-challenge-id")
        if not challenge_id:
            raise RuntimeError("login sem captcha local")

        image = page.locator("#captcha-image")
        image_bytes = await image.screenshot(type="png")
        source_host = host_from_url(start_url)
        start = monotonic()
        solution = await asyncio.to_thread(provider.solve_image_captcha, image_bytes, source_host)
        CAPTCHA_SOLVE_DURATION.observe(monotonic() - start)
        CAPTCHA_SOLVED.inc()
        await page.locator("input[name='captcha_answer']").fill(solution)

    await page.locator("input[name='username']").fill(credentials.username)
    await page.locator("input[name='password']").fill(credentials.password)
    async with page.expect_navigation(wait_until="domcontentloaded"):
        await page.locator("#login-form button[type='submit']").click()
    return True


async def solve_local_challenge(page, start_url: str, provider: CaptchaResolverProvider, proxy: ProxyProfileState) -> None:
    CAPTCHA_DETECTED.inc()
    challenge_id = await page.locator("#captcha-challenge").get_attribute("data-challenge-id")
    image = page.locator("#captcha-image")
    image_bytes = await image.screenshot(type="png")
    source_host = host_from_url(start_url)
    start = monotonic()
    solution = provider.solve_image_captcha(image_bytes, source_host)
    CAPTCHA_SOLVE_DURATION.observe(monotonic() - start)
    CAPTCHA_SOLVED.inc()
    await page.request.post(
        urljoin(start_url, "/captcha/verify"),
        data={
            "challenge_id": challenge_id,
            "answer": solution,
            "session_id": "playwright-session",
            "proxy_id": proxy.name,
        },
    )

