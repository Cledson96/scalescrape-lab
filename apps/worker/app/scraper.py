from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from urllib.parse import urljoin, urlsplit, urlunsplit
import asyncio
import json
import logging
import re

from app.betano import (
    build_betano_record_payload,
    extract_betano_external_id,
    parse_betano_match_datetime,
)
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
from app.free_proxy import get_free_working_proxy


BETANO_HOST = "www.betano.bet.br"
BETANO_FOOTBALL_TODAY_API_PATH = "/api/sport/futebol/jogos-de-hoje/?req=s,stnf,c,mb,mbl"
BOOKS_TO_SCRAPE_HOST = "books.toscrape.com"
GLOBO_HOME_HOST = "www.globo.com"
logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class BetanoDebugArtifactPaths:
    metadata_path: str
    screenshot_path: str
    html_path: str
    metadata_url: str
    screenshot_url: str
    html_url: str


class ScrapeBlocked(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


def mask_proxy_url(proxy_url: str | None) -> str:
    if not proxy_url:
        return "direct"
    parsed = urlsplit(proxy_url)
    if not parsed.username and not parsed.password:
        return proxy_url
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, f"***:***@{host}{port}", "", "", ""))


def betano_block_message(
    status_code: int,
    proxy_url: str | None,
    egress_ip: str | None = None,
    stage: str | None = None,
) -> str:
    details = [f"proxy={mask_proxy_url(proxy_url)}"]
    if egress_ip:
        details.append(f"egress_ip={egress_ip}")
    stage_text = f" durante {stage}" if stage else ""
    return f"bloqueio HTTP {status_code} no Betano{stage_text} ({', '.join(details)})"


def betano_no_league_tabs_message(clickable_count: int, odds_count: int, current_url: str) -> str:
    return (
        "Nenhuma aba de liga encontrada na secao POPULARES do Betano "
        f"(clickables={clickable_count}, odds={odds_count}, url={current_url})"
    )


def betano_debug_artifact_paths(
    *, media_root: str, stem: str, public_api_url: str = ""
) -> BetanoDebugArtifactPaths:
    safe_stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", stem).strip("-") or "betano-debug"
    local_base = Path(media_root) / "betano-debug" / safe_stem
    public_base = f"/media/betano-debug/{safe_stem}"

    def public_url(path: str) -> str:
        if not public_api_url:
            return path
        return f"{public_api_url.rstrip('/')}{path}"

    def local_path(path: Path) -> str:
        return str(path).replace("\\", "/")

    return BetanoDebugArtifactPaths(
        metadata_path=local_path(local_base.with_suffix(".json")),
        screenshot_path=local_path(local_base.with_suffix(".png")),
        html_path=local_path(local_base.with_suffix(".html")),
        metadata_url=public_url(f"{public_base}.json"),
        screenshot_url=public_url(f"{public_base}.png"),
        html_url=public_url(f"{public_base}.html"),
    )


def _message_with_debug_url(message: str, artifact: BetanoDebugArtifactPaths | None) -> str:
    if not artifact:
        return message
    return f"{message}; debug={artifact.metadata_url}"


def _cleanup_betano_debug_artifacts(media_root: str, max_artifacts: int) -> None:
    if max_artifacts <= 0:
        return
    debug_dir = Path(media_root) / "betano-debug"
    if not debug_dir.exists():
        return
    metadata_files = sorted(debug_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for metadata_file in metadata_files[max_artifacts:]:
        stem = metadata_file.with_suffix("")
        for path in (metadata_file, stem.with_suffix(".png"), stem.with_suffix(".html")):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                logger.debug("Nao foi possivel remover artefato antigo do Betano: %s", path)


async def save_betano_debug_artifacts(
    *,
    page,
    media_root: str,
    public_api_url: str,
    label: str,
    status_code: int | None,
    start_url: str,
    proxy_url: str | None,
    egress_ip: str | None,
    max_artifacts: int,
    context: dict | None = None,
) -> BetanoDebugArtifactPaths | None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    artifact = betano_debug_artifact_paths(
        media_root=media_root,
        stem=f"{timestamp}-{label}",
        public_api_url=public_api_url,
    )
    Path(artifact.metadata_path).parent.mkdir(parents=True, exist_ok=True)

    screenshot_error = None
    html_error = None
    page_title = ""
    page_url = ""
    body_excerpt = ""

    try:
        page_url = page.url
    except Exception:
        page_url = ""
    try:
        page_title = await page.title()
    except Exception:
        page_title = ""
    try:
        body_excerpt = (await page.locator("body").inner_text(timeout=2500)).strip()[:1500]
    except Exception:
        body_excerpt = ""
    try:
        await page.screenshot(path=artifact.screenshot_path, full_page=True)
    except Exception as exc:
        screenshot_error = str(exc)
    try:
        Path(artifact.html_path).write_text(await page.content(), encoding="utf-8")
    except Exception as exc:
        html_error = str(exc)

    metadata = {
        "label": label,
        "status_code": status_code,
        "start_url": start_url,
        "page_url": page_url,
        "title": page_title,
        "body_excerpt": body_excerpt,
        "proxy": mask_proxy_url(proxy_url),
        "egress_ip": egress_ip,
        "metadata_url": artifact.metadata_url,
        "screenshot_url": artifact.screenshot_url if screenshot_error is None else None,
        "html_url": artifact.html_url if html_error is None else None,
        "screenshot_error": screenshot_error,
        "html_error": html_error,
        "context": context or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    Path(artifact.metadata_path).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    _cleanup_betano_debug_artifacts(media_root, max_artifacts)
    logger.info("Betano debug salvo em %s", artifact.metadata_url)
    return artifact


async def maybe_save_betano_debug_artifacts(**kwargs) -> BetanoDebugArtifactPaths | None:
    try:
        return await save_betano_debug_artifacts(**kwargs)
    except Exception as exc:  # pragma: no cover - diagnostico nao deve derrubar o scraping
        logger.warning("Falha ao salvar debug do Betano: %s", exc)
        return None


async def read_browser_egress_ip(page, proxy_url: str | None) -> str | None:  # noqa: ANN001
    if not proxy_url:
        return None
    try:
        response = await page.goto("https://api.ipify.org?format=text", wait_until="domcontentloaded", timeout=15000)
        status = response.status if response else 0
        if status >= 400:
            logger.warning("Falha ao consultar IP de saida pelo proxy Betano: HTTP %s", status)
            return None
        body = (await page.locator("body").inner_text(timeout=5000)).strip()
        return body[:80] if body else None
    except Exception as exc:  # pragma: no cover - diagnostico defensivo de rede
        logger.warning("Falha ao consultar IP de saida pelo proxy Betano: %s", exc)
        return None


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
    public_api_url: str = "http://localhost:8000",
    globo_max_articles: int = 12,
    betano_max_leagues: int = 10,
    betano_proxy_url: str = "",
    betano_debug_artifacts: bool = False,
    betano_debug_max_artifacts: int = 40,
) -> list[ScrapedRecord]:
    from playwright.async_api import async_playwright


    records: list[ScrapedRecord] = []
    async with async_playwright() as playwright:
        if host_from_url(start_url) == BETANO_HOST:
            # Betano's sports API currently works more reliably from a fresh
            # context. Reusing homepage/session cookies can turn API calls into 403.
            session_path = ""
            storage_state = None

            if betano_proxy_url == "auto":
                betano_proxy_url = await get_free_working_proxy()

            betano_browser = await playwright.chromium.launch(
                headless=True,
                proxy={"server": betano_proxy_url} if betano_proxy_url else None,
                args=[
                    "--headless=new",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--window-size=1280,800",
                ],
            )
            betano_context = await betano_browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
                extra_http_headers={
                    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                },
                storage_state=storage_state,
            )
            # Align browser-exposed fields with a regular Chromium session.
            await betano_context.add_init_script("""
                // Avoid exposing automation-only webdriver state.
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

                // Provide Chrome runtime fields expected by client-side scripts.
                window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};

                // Populate plugin metadata commonly present in desktop Chromium.
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                        {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                        {name: 'Native Client', filename: 'internal-nacl-plugin'},
                    ],
                });

                // Keep locale signals consistent with the request headers.
                Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});

                // Match notification permission semantics from full Chromium.
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) =>
                    parameters.name === 'notifications'
                        ? Promise.resolve({state: Notification.permission})
                        : originalQuery(parameters);

                // Keep iframe runtime fields consistent with the top-level window.
                const origGetter = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow').get;
                Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                    get: function() {
                        const result = origGetter.call(this);
                        if (!result) return result;
                        try { result.chrome = window.chrome; } catch(e) {}
                        return result;
                    }
                });

                // Use stable WebGL vendor strings for reproducible sessions.
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter.call(this, parameter);
                };

                // Normalize network information exposed to page scripts.
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({effectiveType: '4g', rtt: 50, downlink: 10, saveData: false}),
                });

                // Expose a realistic desktop CPU profile.
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});

                // Keep platform aligned with the selected user agent.
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            """)
            betano_page = await betano_context.new_page()
            betano_page.set_default_timeout(page_timeout_seconds * 1000)
            betano_egress_ip = await read_browser_egress_ip(betano_page, betano_proxy_url)
            logger.info(
                "Betano browser configurado com proxy=%s egress_ip=%s storage_state=%s",
                mask_proxy_url(betano_proxy_url),
                betano_egress_ip or "desconhecido",
                "sim" if storage_state else "nao",
            )
            try:
                records = await scrape_betano_football(
                    page=betano_page,
                    context=betano_context,
                    start_url=start_url,
                    proxy=proxy,
                    max_leagues=betano_max_leagues,
                    session_path=session_path,
                    media_root=media_root,
                    public_api_url=public_api_url,
                    debug_artifacts=betano_debug_artifacts,
                    debug_max_artifacts=betano_debug_max_artifacts,
                    betano_proxy_url=betano_proxy_url,
                    betano_egress_ip=betano_egress_ip,
                )
            finally:
                await betano_browser.close()
            return records

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


async def _browser_paced_click(element, page) -> None:
    """Execute a browser-paced click with scroll, hover and small timing variance."""
    import random
    await element.scroll_into_view_if_needed()
    await page.wait_for_timeout(random.randint(200, 500))
    await element.hover()
    await page.wait_for_timeout(random.randint(100, 350))
    await element.click()


async def _accept_betano_age_verification(page) -> bool:  # noqa: ANN001
    selectors = [
        '#age-verification-modal [data-qa="age-verification-modal-ok-button"]',
        '#age-verification-modal button:has-text("Sim")',
    ]
    for selector in selectors:
        button = page.locator(selector).first
        try:
            if await button.count() == 0:
                continue
            await _browser_paced_click(button, page)
            try:
                await page.locator("#age-verification-modal").wait_for(state="hidden", timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)
            return True
        except Exception:
            continue
    return False


async def _close_betano_landing_modal(page) -> bool:  # noqa: ANN001
    selectors = [
        '[data-testid="landing-modal-close-button"]',
        '[data-testid="landing-modal"] button[aria-label="Close modal"]',
    ]
    for selector in selectors:
        button = page.locator(selector).first
        try:
            if await button.count() == 0:
                continue
            await _browser_paced_click(button, page)
            try:
                await page.locator('[data-testid="landing-modal"]').wait_for(state="hidden", timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(500)
            return True
        except Exception:
            continue
    return False


async def _reset_betano_browser_state(page, context, session_path: str = "") -> bool:  # noqa: ANN001
    removed_session = False
    try:
        await context.clear_cookies()
    except Exception:
        pass

    try:
        await page.evaluate("""() => {
            window.localStorage?.clear();
            window.sessionStorage?.clear();
        }""")
    except Exception:
        pass

    if session_path:
        try:
            path = Path(session_path)
            if path.exists():
                path.unlink()
                removed_session = True
        except Exception:
            pass
    return removed_session


async def _click_betano_football_from_homepage(page) -> dict:  # noqa: ANN001
    result = {
        "clicked": False,
        "selector": "",
        "href": "",
        "mouse_response_status": 0,
        "mouse_response_url": "",
        "keyboard_response_status": 0,
        "keyboard_response_url": "",
        "url_after_click": "",
        "error": "",
    }
    selectors = [
        'a[href*="/sport/futebol"]',
        'a:has-text("Futebol")',
        '[role="link"]:has-text("Futebol")',
        'text="Futebol"',
    ]
    for selector in selectors:
        locator = page.locator(selector)
        try:
            count = await locator.count()
        except Exception:
            continue
        for index in range(min(count, 10)):
            candidate = locator.nth(index)
            try:
                if not await candidate.is_visible(timeout=1000):
                    continue
                result["selector"] = selector
                result["href"] = await candidate.get_attribute("href") or ""
                try:
                    async with page.expect_response(lambda response: "/sport/futebol" in response.url, timeout=12000) as response_info:
                        await _browser_paced_click(candidate, page)
                    response = await response_info.value
                    result["mouse_response_status"] = response.status
                    result["mouse_response_url"] = response.url
                except Exception as exc:
                    result["error"] = str(exc)

                if "/sport/futebol" not in page.url:
                    try:
                        await candidate.focus()
                        async with page.expect_response(
                            lambda response: "/sport/futebol" in response.url,
                            timeout=12000,
                        ) as keyboard_response_info:
                            await page.keyboard.press("Enter")
                        keyboard_response = await keyboard_response_info.value
                        result["keyboard_response_status"] = keyboard_response.status
                        result["keyboard_response_url"] = keyboard_response.url
                    except Exception as exc:
                        if not result["error"]:
                            result["error"] = str(exc)

                await page.wait_for_timeout(1500)
                result["url_after_click"] = page.url
                result["clicked"] = bool(
                    result["mouse_response_status"]
                    or result["keyboard_response_status"]
                    or "/sport/futebol" in page.url
                )
                return result
            except Exception as exc:
                result["error"] = str(exc)
                continue
    result["url_after_click"] = page.url
    if not result["error"]:
        result["error"] = "link Futebol visivel nao encontrado"
    return result


def _betano_football_today_api_url(football_url: str) -> str:
    base_url = football_url.split("/sport/")[0].rstrip("/")
    return f"{base_url}{BETANO_FOOTBALL_TODAY_API_PATH}"


def _betano_api_match_datetime(start_time_ms: int | float | None) -> dict:
    if not start_time_ms:
        return {"date_str": "", "time_str": "", "is_live": False, "datetime_iso": ""}
    try:
        parsed = datetime.fromtimestamp(float(start_time_ms) / 1000, timezone.utc)
    except (TypeError, ValueError, OSError):
        return {"date_str": "", "time_str": "", "is_live": False, "datetime_iso": ""}
    return {
        "date_str": parsed.strftime("%d/%m"),
        "time_str": parsed.strftime("%H:%M"),
        "is_live": False,
        "datetime_iso": parsed.isoformat(),
    }


def _betano_api_teams(event: dict) -> tuple[str, str]:
    participants = event.get("participants") or []
    if len(participants) >= 2:
        home = str(participants[0].get("name") or "").strip()
        away = str(participants[1].get("name") or "").strip()
        if home and away:
            return home, away

    name = str(event.get("name") or event.get("shortName") or "").strip()
    for separator in (" - ", " x ", " vs "):
        if separator in name:
            home, away = name.split(separator, 1)
            return home.strip(), away.strip()
    return name, ""


def _betano_api_result_market(event: dict) -> dict | None:
    for market in event.get("markets") or []:
        selections = market.get("selections") or []
        selection_names = {str(selection.get("name") or "").strip() for selection in selections}
        if {"1", "X", "2"}.issubset(selection_names):
            return market
    return None


def _betano_api_selection_price(market: dict, name: str, column_index: int) -> str:
    selections = market.get("selections") or []
    for selection in selections:
        if str(selection.get("name") or "").strip() == name:
            return str(selection.get("price") or "")
    for selection in selections:
        if selection.get("columnIndex") == column_index:
            return str(selection.get("price") or "")
    return ""


def _build_betano_api_records(
    *,
    payload: dict,
    proxy: ProxyProfileState,
    max_leagues: int,
    base_url: str,
    extracted_at: str,
) -> list[ScrapedRecord]:
    records: list[ScrapedRecord] = []
    blocks = payload.get("data", {}).get("blocks", [])
    leagues = blocks[:max_leagues] if max_leagues > 0 else blocks

    for block in leagues:
        championship = str(block.get("name") or block.get("shortName") or "Futebol").strip()
        for event in block.get("events") or []:
            market = _betano_api_result_market(event)
            if not market:
                continue
            home_team, away_team = _betano_api_teams(event)
            if not home_team or not away_team:
                continue

            match_datetime = _betano_api_match_datetime(event.get("startTime"))
            match_url = urljoin(base_url, str(event.get("url") or ""))
            odd_home = _betano_api_selection_price(market, "1", 0)
            odd_draw = _betano_api_selection_price(market, "X", 1)
            odd_away = _betano_api_selection_price(market, "2", 2)
            raw_data = build_betano_record_payload(
                home_team=home_team,
                away_team=away_team,
                championship=championship,
                market_type=str(market.get("name") or "Resultado da partida"),
                odd_home=odd_home,
                odd_draw=odd_draw,
                odd_away=odd_away,
                match_datetime=match_datetime,
                match_url=match_url,
                extracted_at=extracted_at,
            )
            raw_data.update(
                {
                    "collection_method": "betano-api",
                    "api_event_id": event.get("id"),
                    "api_market_id": market.get("id"),
                    "proxy_profile": proxy.name,
                }
            )
            external_id = f"betano-{event.get('id')}" if event.get("id") else extract_betano_external_id(
                home_team,
                away_team,
                championship,
                match_datetime.get("datetime_iso", ""),
            )
            records.append(
                ScrapedRecord(
                    external_id=external_id,
                    title=f"{home_team} x {away_team}",
                    detail_url=match_url,
                    raw_data=raw_data,
                )
            )

    return records


async def _scrape_betano_football_api(
    *,
    page,
    context,
    football_url: str,
    start_url: str,
    proxy: ProxyProfileState,
    max_leagues: int,
    media_root: str,
    public_api_url: str,
    debug_artifacts: bool,
    debug_max_artifacts: int,
    betano_proxy_url: str | None,
    betano_egress_ip: str | None,
) -> list[ScrapedRecord]:
    await _reset_betano_browser_state(page, context)
    api_url = _betano_football_today_api_url(football_url)
    response = await page.goto(api_url, wait_until="domcontentloaded", timeout=20000)
    status = response.status if response else 0

    if status in (403, 429):
        artifact = None
        if debug_artifacts:
            artifact = await maybe_save_betano_debug_artifacts(
                page=page,
                media_root=media_root,
                public_api_url=public_api_url,
                label=f"api-football-http-{status}",
                status_code=status,
                start_url=start_url,
                proxy_url=betano_proxy_url,
                egress_ip=betano_egress_ip,
                max_artifacts=debug_max_artifacts,
                context={"stage": "api-football", "api_url": api_url},
            )
        raise ScrapeBlocked(
            status,
            _message_with_debug_url(betano_block_message(status, betano_proxy_url, betano_egress_ip, "api futebol"), artifact),
        )

    if status >= 400:
        return []

    body = (await page.locator("body").inner_text(timeout=5000)).strip()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return []

    records = _build_betano_api_records(
        payload=payload,
        proxy=proxy,
        max_leagues=max_leagues,
        base_url=football_url.split("/sport/")[0].rstrip("/") + "/",
        extracted_at=datetime.now(timezone.utc).isoformat(),
    )
    if records:
        logger.info("Betano API retornou %s jogos", len(records))
    return records


async def scrape_betano_football(
    *,
    page,
    context,
    start_url: str,
    proxy: ProxyProfileState,
    max_leagues: int = 10,
    session_path: str = "",
    media_root: str = "/app/media",
    public_api_url: str = "http://localhost:8000",
    debug_artifacts: bool = False,
    debug_max_artifacts: int = 40,
    betano_proxy_url: str | None = None,
    betano_egress_ip: str | None = None,
) -> list[ScrapedRecord]:
    """Scrape football odds from Betano's POPULARES section.

    Navigates to the football page, iterates through each popular league tab,
    and collects match data with 1/X/2 odds for each visible game.
    Uses browser-paced interactions and persists session cookies between runs.
    """
    import random
    from datetime import datetime, timezone

    football_url = start_url
    if not football_url.rstrip("/").endswith("/sport/futebol"):
        football_url = start_url.rstrip("/") + "/sport/futebol/"

    api_records = await _scrape_betano_football_api(
        page=page,
        context=context,
        football_url=football_url,
        start_url=start_url,
        proxy=proxy,
        max_leagues=max_leagues,
        media_root=media_root,
        public_api_url=public_api_url,
        debug_artifacts=debug_artifacts,
        debug_max_artifacts=debug_max_artifacts,
        betano_proxy_url=betano_proxy_url,
        betano_egress_ip=betano_egress_ip,
    )
    if api_records:
        return api_records

    # Build homepage session state before direct football navigation; some
    # egress networks receive access-control responses on deep links.
    homepage = football_url.split("/sport/")[0] + "/"
    homepage_status = 0
    homepage_error = ""
    homepage_retry_status = 0
    homepage_retry_error = ""
    session_file_removed = False
    accepted_age = False
    closed_landing_modal = False
    try:
        homepage_response = await page.goto(homepage, wait_until="domcontentloaded", timeout=15000)
        homepage_status = homepage_response.status if homepage_response else 0
        await page.wait_for_timeout(random.randint(2000, 3500))
        accepted_age = await _accept_betano_age_verification(page)
        closed_landing_modal = await _close_betano_landing_modal(page)
    except Exception as exc:
        homepage_error = str(exc)

    if homepage_status in (403, 429):
        session_file_removed = await _reset_betano_browser_state(page, context, session_path)
        try:
            await page.wait_for_timeout(random.randint(1500, 2500))
            homepage_response = await page.goto(homepage, wait_until="domcontentloaded", timeout=15000)
            homepage_retry_status = homepage_response.status if homepage_response else 0
            homepage_status = homepage_retry_status
            await page.wait_for_timeout(random.randint(2000, 3500))
            accepted_age = await _accept_betano_age_verification(page)
            closed_landing_modal = await _close_betano_landing_modal(page)
        except Exception as exc:
            homepage_retry_error = str(exc)

    if homepage_status in (403, 429):
        artifact = None
        if debug_artifacts:
            artifact = await maybe_save_betano_debug_artifacts(
                page=page,
                media_root=media_root,
                public_api_url=public_api_url,
                label=f"homepage-http-{homepage_status}",
                status_code=homepage_status,
                start_url=start_url,
                proxy_url=betano_proxy_url,
                egress_ip=betano_egress_ip,
                max_artifacts=debug_max_artifacts,
                context={
                    "stage": "homepage",
                    "homepage_url": homepage,
                    "homepage_error": homepage_error,
                    "homepage_retry_status": homepage_retry_status,
                    "homepage_retry_error": homepage_retry_error,
                    "session_file_removed": session_file_removed,
                    "accepted_age": accepted_age,
                    "closed_landing_modal": closed_landing_modal,
                },
            )
        raise ScrapeBlocked(
            homepage_status,
            _message_with_debug_url(
                betano_block_message(homepage_status, betano_proxy_url, betano_egress_ip, "homepage"), artifact
            ),
        )

    # Prefer a fresh browser-paced click from the loaded homepage. If the SPA does
    # not navigate, fall back to the direct football URL and keep diagnostics.
    football_click = await _click_betano_football_from_homepage(page)

    # Now navigate to the actual football page when the homepage click did not land there.
    football_error = ""
    try:
        if "/sport/futebol" in page.url:
            response = None
        else:
            response = await page.goto(football_url, wait_until="domcontentloaded")
    except Exception as exc:
        football_error = str(exc)
        artifact = None
        if debug_artifacts:
            artifact = await maybe_save_betano_debug_artifacts(
                page=page,
                media_root=media_root,
                public_api_url=public_api_url,
                label="football-navigation-error",
                status_code=None,
                start_url=start_url,
                proxy_url=betano_proxy_url,
                egress_ip=betano_egress_ip,
                max_artifacts=debug_max_artifacts,
                context={
                    "stage": "football",
                    "football_url": football_url,
                    "homepage_status": homepage_status,
                    "homepage_error": homepage_error,
                    "homepage_retry_status": homepage_retry_status,
                    "homepage_retry_error": homepage_retry_error,
                    "session_file_removed": session_file_removed,
                    "accepted_age": accepted_age,
                    "closed_landing_modal": closed_landing_modal,
                    "football_click": football_click,
                    "navigation_error": football_error,
                },
            )
        raise RuntimeError(_message_with_debug_url(f"falha ao navegar Betano futebol: {football_error}", artifact))
    status = response.status if response else 200

    # Retry access-control responses after JS execution and cookie warmup.
    for attempt in range(3):
        if status not in (403, 429):
            break
        wait_ms = (attempt + 1) * 5000  # 5s, 10s, 15s
        await page.wait_for_timeout(wait_ms)
        response = await page.reload(wait_until="domcontentloaded")
        status = response.status if response else 0

    if status in (403, 429):
        artifact = None
        if debug_artifacts:
            artifact = await maybe_save_betano_debug_artifacts(
                page=page,
                media_root=media_root,
                public_api_url=public_api_url,
                label=f"http-{status}",
                status_code=status,
                start_url=start_url,
                proxy_url=betano_proxy_url,
                egress_ip=betano_egress_ip,
                max_artifacts=debug_max_artifacts,
                context={
                    "stage": "football",
                    "football_url": football_url,
                    "homepage_status": homepage_status,
                    "homepage_error": homepage_error,
                    "homepage_retry_status": homepage_retry_status,
                    "homepage_retry_error": homepage_retry_error,
                    "session_file_removed": session_file_removed,
                    "accepted_age": accepted_age,
                    "closed_landing_modal": closed_landing_modal,
                    "football_click": football_click,
                },
            )
        raise ScrapeBlocked(
            status,
            _message_with_debug_url(betano_block_message(status, betano_proxy_url, betano_egress_ip, "futebol"), artifact),
        )

    # Allow dynamic modules and lazy-loaded odds to settle after navigation.
    await page.wait_for_timeout(random.randint(2500, 4000))
    closed_landing_modal = await _close_betano_landing_modal(page) or closed_landing_modal

    # Incremental scroll also triggers lazy-loaded content.
    for scroll_y in (200, 450, 700):
        await page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        await page.wait_for_timeout(random.randint(300, 600))
    # Return to the POPULARES section before collecting league cards.
    await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    await page.wait_for_timeout(random.randint(400, 800))

    # Save session cookies after first successful page load
    if session_path:
        try:
            Path(session_path).parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=session_path)
        except Exception:
            pass

    records: list[ScrapedRecord] = []

    league_keywords = [
        "brasileir", "premier", "libertadores", "serie",
        "copa", "league", "bundesliga", "liga", "ligue",
        "championship", "sul-american", "feminino", "nbb",
        "la liga", "serie a", "eredivisie",
    ]

    # Find all clickable elements and filter by league-name keywords
    all_clickables = page.locator(
        'div[role="button"], button, a[role="tab"], '
        '[class*="league"] div, [class*="pill"], [class*="chip"], [class*="tab-item"]'
    )
    clickable_count = await all_clickables.count()
    league_tabs = []
    for i in range(clickable_count):
        el = all_clickables.nth(i)
        try:
            text = (await el.inner_text(timeout=2000)).strip()
            if text and any(kw in text.lower() for kw in league_keywords):
                if len(text) < 60:
                    league_tabs.append((el, text))
        except Exception:
            continue

    # Deduplicate by text (keep first occurrence)
    seen_names: set[str] = set()
    unique_tabs = []
    for el, name in league_tabs:
        if name not in seen_names:
            seen_names.add(name)
            unique_tabs.append((el, name))
    league_tabs = unique_tabs

    leagues_to_scrape = min(len(league_tabs), max_leagues)
    if leagues_to_scrape == 0:
        extracted_at = datetime.now(timezone.utc).isoformat()
        records = await _extract_betano_visible_matches(
            page=page,
            championship="Futebol - mercados populares",
            market_type="Resultado da partida",
            proxy=proxy,
            extracted_at=extracted_at,
        )
        if records:
            logger.info("Betano sem abas de liga; extraidos %s jogos da tela atual", len(records))
            return records
        visible_odds_count = await _count_betano_visible_odds(page)
        message = betano_no_league_tabs_message(clickable_count, visible_odds_count, page.url)
        artifact = None
        if debug_artifacts:
            artifact = await maybe_save_betano_debug_artifacts(
                page=page,
                media_root=media_root,
                public_api_url=public_api_url,
                label="no-league-tabs",
                status_code=status,
                start_url=start_url,
                proxy_url=betano_proxy_url,
                egress_ip=betano_egress_ip,
                max_artifacts=debug_max_artifacts,
                context={
                    "stage": "extract",
                    "football_url": football_url,
                    "homepage_status": homepage_status,
                    "homepage_error": homepage_error,
                    "homepage_retry_status": homepage_retry_status,
                    "homepage_retry_error": homepage_retry_error,
                    "session_file_removed": session_file_removed,
                    "accepted_age": accepted_age,
                    "closed_landing_modal": closed_landing_modal,
                    "football_click": football_click,
                },
            )
        raise RuntimeError(_message_with_debug_url(message, artifact))

    for tab_el, championship in league_tabs[:leagues_to_scrape]:
        extracted_at = datetime.now(timezone.utc).isoformat()

        try:
            # Browser-paced click: scroll, hover, timing variance and click.
            await _browser_paced_click(tab_el, page)
            # Wait between tabs to let dynamic odds panels stabilize.
            await page.wait_for_timeout(random.randint(1500, 3500))

            market_type = "Resultado da partida"

            records.extend(
                await _extract_betano_visible_matches(
                    page=page,
                    championship=championship,
                    market_type=market_type,
                    proxy=proxy,
                    extracted_at=extracted_at,
                )
            )

        except Exception:
            continue

    return records


async def _count_betano_visible_odds(page) -> int:  # noqa: ANN001
    buttons = await _betano_visible_odd_buttons(page)
    return len(buttons)


async def _betano_visible_odd_buttons(page) -> list:  # noqa: ANN001
    import re

    # Extract matches using odds buttons as anchors. Betano odds buttons may
    # expose aria-labels, selection classes, or only plain numeric text.
    odds_btns = page.locator(
        '[aria-label*="Bet on"][aria-label*="odds"], '
        '[aria-label*="apostar"][aria-label*="odds"], '
        'div.selections__selection[role="button"]'
    )
    odds_count = await odds_btns.count()
    if odds_count >= 3:
        return [odds_btns.nth(index) for index in range(odds_count)]

    fallback_odds = []
    role_buttons = page.locator('[role="button"], button')
    role_count = await role_buttons.count()
    for index in range(role_count):
        try:
            text = (await role_buttons.nth(index).inner_text(timeout=1000)).strip()
            if re.match(r'^\d+[.,]\d{2}$', text):
                fallback_odds.append(role_buttons.nth(index))
        except Exception:
            continue
    return fallback_odds


async def _extract_betano_visible_matches(
    *,
    page,
    championship: str,
    market_type: str,
    proxy: ProxyProfileState,
    extracted_at: str,
) -> list[ScrapedRecord]:
    records: list[ScrapedRecord] = []
    odds_buttons = await _betano_visible_odd_buttons(page)
    for group_index in range(0, len(odds_buttons) - 2, 3):
        try:
            record = await _build_match_from_odds_group(
                page=page,
                btn_home=odds_buttons[group_index],
                btn_draw=odds_buttons[group_index + 1],
                btn_away=odds_buttons[group_index + 2],
                championship=championship,
                market_type=market_type,
                proxy=proxy,
                extracted_at=extracted_at,
            )
            if record:
                records.append(record)
        except Exception:
            continue
    return records


async def _build_match_from_odds_group(
    *,
    page,
    btn_home,
    btn_draw,
    btn_away,
    championship: str,
    market_type: str,
    proxy: ProxyProfileState,
    extracted_at: str,
) -> ScrapedRecord | None:
    """Build a ScrapedRecord from a group of 3 odds buttons (1/X/2).

    Navigates up the DOM from the first button to find team names,
    date/time, and match URL in the parent event container.
    """
    import re

    odd_home = (await btn_home.inner_text()).strip()
    odd_draw = (await btn_draw.inner_text()).strip()
    odd_away = (await btn_away.inner_text()).strip()

    # Navigate up to find the event container with team names
    # Try multiple ancestor strategies
    parent = None
    for xpath in [
        "xpath=ancestor::div[contains(@class,'event') or contains(@class,'match') or contains(@class,'row')][1]",
        "xpath=ancestor::div[.//a[contains(@href,'/odds/')]][1]",
        "xpath=ancestor::div[count(.//div[@role='button'])>=3][1]",
    ]:
        candidate = btn_home.locator(xpath)
        if await candidate.count() > 0:
            parent = candidate.first
            break

    if not parent:
        return None

    parent_text = await parent.inner_text()
    lines = [l.strip() for l in parent_text.split("\n") if l.strip()]

    home_team = ""
    away_team = ""
    match_datetime_raw = ""
    match_url = ""

    # Try to find match URL from an <a> in the parent
    match_link = parent.locator("a[href*='/odds/']")
    if await match_link.count() > 0:
        match_url = await match_link.first.get_attribute("href") or ""

    # Parse lines for date/time and team names
    team_candidates = []
    for line in lines:
        if re.match(r'^\d+\.\d{2}$', line):
            continue
        if line in ("1", "X", "2"):
            continue
        if "AO VIVO" in line.upper():
            match_datetime_raw = "AO VIVO"
            continue
        if re.match(r'^\d{2}/\d{2}\s+\d{2}:\d{2}', line):
            match_datetime_raw = line
            continue
        if line.lower() in ("hoje", "amanhã", "amanha"):
            match_datetime_raw = line
            continue
        if any(kw in line.lower() for kw in [
            "resultado", "mais/menos", "ambos", "chance",
            "escanteios", "intervalo", "visitar", "populares",
            "empate", "dupla",
        ]):
            continue
        if len(line) > 1 and not re.match(r'^[\d.,]+$', line):
            team_candidates.append(line)

    if len(team_candidates) >= 2:
        home_team = team_candidates[0]
        away_team = team_candidates[1]
    elif len(team_candidates) == 1:
        home_team = team_candidates[0]

    if not home_team:
        return None

    match_datetime = parse_betano_match_datetime(match_datetime_raw)
    external_id = extract_betano_external_id(
        home_team, away_team, championship, match_datetime_raw
    )
    payload = build_betano_record_payload(
        home_team=home_team,
        away_team=away_team,
        championship=championship,
        market_type=market_type,
        odd_home=odd_home,
        odd_draw=odd_draw,
        odd_away=odd_away,
        match_datetime=match_datetime,
        match_url=match_url,
        extracted_at=extracted_at,
    )
    title = f"{home_team} vs {away_team}"
    return ScrapedRecord(
        external_id=external_id,
        title=title,
        detail_url=match_url,
        raw_data={**payload, "proxy": proxy.name},
    )



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

