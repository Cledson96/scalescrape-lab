from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from urllib.parse import urljoin
import asyncio

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


BETANO_HOST = "www.betano.bet.br"
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
    betano_max_leagues: int = 10,
    betano_proxy_url: str = "",
) -> list[ScrapedRecord]:
    from playwright.async_api import async_playwright


    records: list[ScrapedRecord] = []
    async with async_playwright() as playwright:
        if host_from_url(start_url) == BETANO_HOST:
            # Betano has bot detection — stealth browser + cookie session persistence
            session_path = str(Path(media_root) / "betano_session.json")
            storage_state = session_path if Path(session_path).exists() else None

            betano_browser = await playwright.chromium.launch(
                headless=True,
                proxy={"server": betano_proxy_url} if betano_proxy_url else None,
                args=[
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
            # Comprehensive stealth: patch all major headless fingerprints
            await betano_context.add_init_script("""
                // Hide webdriver flag
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

                // Fake chrome runtime (real Chrome always has this)
                window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};

                // Fake plugins (headless has 0 plugins)
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                        {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                        {name: 'Native Client', filename: 'internal-nacl-plugin'},
                    ],
                });

                // Fake languages
                Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});

                // Fake permissions API (headless denies all)
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) =>
                    parameters.name === 'notifications'
                        ? Promise.resolve({state: Notification.permission})
                        : originalQuery(parameters);

                // Fix iframe contentWindow detection
                const origGetter = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow').get;
                Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                    get: function() {
                        const result = origGetter.call(this);
                        if (!result) return result;
                        try { result.chrome = window.chrome; } catch(e) {}
                        return result;
                    }
                });

                // Fake WebGL renderer (headless shows "Google SwiftShader")
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter.call(this, parameter);
                };

                // Fake connection (headless shows odd rtt values)
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({effectiveType: '4g', rtt: 50, downlink: 10, saveData: false}),
                });

                // Fake hardwareConcurrency (headless often shows 1 or 2)
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});

                // Fake platform
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            """)
            betano_page = await betano_context.new_page()
            betano_page.set_default_timeout(page_timeout_seconds * 1000)
            try:
                records = await scrape_betano_football(
                    page=betano_page,
                    context=betano_context,
                    start_url=start_url,
                    proxy=proxy,
                    max_leagues=betano_max_leagues,
                    session_path=session_path,
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


async def _human_click(element, page) -> None:
    """Simulate a human-like click: scroll into view, hover, random delay, then click.

    This makes interactions harder to fingerprint as automated bot behavior.
    """
    import random
    await element.scroll_into_view_if_needed()
    await page.wait_for_timeout(random.randint(200, 500))
    await element.hover()
    await page.wait_for_timeout(random.randint(100, 350))
    await element.click()


async def scrape_betano_football(
    *,
    page,
    context,
    start_url: str,
    proxy: ProxyProfileState,
    max_leagues: int = 10,
    session_path: str = "",
) -> list[ScrapedRecord]:
    """Scrape football odds from Betano's POPULARES section.

    Navigates to the football page, iterates through each popular league tab,
    and collects match data with 1/X/2 odds for each visible game.
    Uses human-like interactions and persists session cookies between runs.
    """
    import random
    import re
    from datetime import datetime, timezone

    football_url = start_url
    if not football_url.rstrip("/").endswith("/sport/futebol"):
        football_url = start_url.rstrip("/") + "/sport/futebol/"

    # Navigate to the homepage first to build a natural session/cookies,
    # then navigate to football — direct deep links from datacenter IPs get blocked.
    homepage = football_url.split("/sport/")[0] + "/"
    try:
        await page.goto(homepage, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(random.randint(2000, 3500))
    except Exception:
        pass  # Homepage may redirect or timeout, that's fine

    # Now navigate to the actual football page
    response = await page.goto(football_url, wait_until="domcontentloaded")
    status = response.status if response else 0

    # Retry logic: some anti-bot systems resolve after JS challenge or cookie warmup
    for attempt in range(3):
        if status not in (403, 429):
            break
        wait_ms = (attempt + 1) * 5000  # 5s, 10s, 15s
        await page.wait_for_timeout(wait_ms)
        response = await page.reload(wait_until="domcontentloaded")
        status = response.status if response else 0

    if status in (403, 429):
        raise ScrapeBlocked(status, f"bloqueio HTTP {status} no Betano")

    # Simulate a human reading the page after it loads
    await page.wait_for_timeout(random.randint(2500, 4000))

    # Scroll down slowly to simulate reading — also triggers lazy-loaded content
    for scroll_y in (200, 450, 700):
        await page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        await page.wait_for_timeout(random.randint(300, 600))
    # Scroll back up to the POPULARES section
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
        raise RuntimeError("Nenhuma aba de liga encontrada na seção POPULARES do Betano")

    for tab_el, championship in league_tabs[:leagues_to_scrape]:
        extracted_at = datetime.now(timezone.utc).isoformat()

        try:
            # Human-like click: scroll → hover → random delay → click
            await _human_click(tab_el, page)
            # Random wait between tabs (1.5s–3.5s) like a human reading content
            await page.wait_for_timeout(random.randint(1500, 3500))

            market_type = "Resultado da partida"

            # Extract matches using the odds buttons as anchors.
            # Betano odds buttons have aria-label like "Bet on 1 with odds 4.75."
            # They appear as div[role="button"] or button elements.
            odds_btns = page.locator(
                '[aria-label*="Bet on"][aria-label*="odds"], '
                '[aria-label*="apostar"][aria-label*="odds"], '
                'div.selections__selection[role="button"]'
            )
            odds_count = await odds_btns.count()

            if odds_count < 3:
                # Fallback: try generic odds pattern via text
                odds_btns = page.locator('[role="button"]')
                fallback_odds = []
                fc = await odds_btns.count()
                for fi in range(fc):
                    try:
                        ft = (await odds_btns.nth(fi).inner_text(timeout=1000)).strip()
                        if re.match(r'^\d+\.\d{2}$', ft):
                            fallback_odds.append(odds_btns.nth(fi))
                    except Exception:
                        continue
                if len(fallback_odds) >= 3:
                    # Process in groups of 3
                    for gi in range(0, len(fallback_odds) - 2, 3):
                        try:
                            record = await _build_match_from_odds_group(
                                page=page,
                                btn_home=fallback_odds[gi],
                                btn_draw=fallback_odds[gi + 1],
                                btn_away=fallback_odds[gi + 2],
                                championship=championship,
                                market_type=market_type,
                                proxy=proxy,
                                extracted_at=extracted_at,
                            )
                            if record:
                                records.append(record)
                        except Exception:
                            continue
                continue

            # Group odds in sets of 3 (1/X/2)
            for gi in range(0, odds_count - 2, 3):
                try:
                    record = await _build_match_from_odds_group(
                        page=page,
                        btn_home=odds_btns.nth(gi),
                        btn_draw=odds_btns.nth(gi + 1),
                        btn_away=odds_btns.nth(gi + 2),
                        championship=championship,
                        market_type=market_type,
                        proxy=proxy,
                        extracted_at=extracted_at,
                    )
                    if record:
                        records.append(record)
                except Exception:
                    continue

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

