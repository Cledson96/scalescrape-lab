from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from urllib.parse import urljoin

from app.captcha.base import CaptchaResolverProvider
from app.metrics import CAPTCHA_DETECTED, CAPTCHA_SOLVE_DURATION, CAPTCHA_SOLVED
from app.policy import host_from_url
from app.proxy.manager import ProxyProfileState


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
        start = monotonic()
        token = provider.solve_recaptcha(sitekey, page_url, source_host)
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
        solution = provider.solve_image_captcha(image_bytes, source_host)
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

