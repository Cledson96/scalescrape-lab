from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import logging
import random

from app.proxy.manager import ProxyProfileState
from app.scraping.contracts import ScrapedRecord, ScrapeBlocked
from app.scraping.runtime.debug_artifacts import (
    _message_with_debug_url,
    betano_block_message,
    betano_no_league_tabs_message,
    maybe_save_betano_debug_artifacts,
)
from app.scraping.sources.betano_api import scrape_betano_football_api
from app.scraping.sources.betano_dom import count_betano_visible_odds, extract_betano_visible_matches
from app.scraping.sources.betano_navigation import (
    accept_betano_age_verification,
    browser_paced_click,
    click_betano_football_from_homepage,
    close_betano_landing_modal,
    reset_betano_browser_state,
)

BETANO_HOST = "www.betano.bet.br"
logger = logging.getLogger(__name__)


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
    football_url = start_url
    if not football_url.rstrip("/").endswith("/sport/futebol"):
        football_url = start_url.rstrip("/") + "/sport/futebol/"

    api_records = await scrape_betano_football_api(
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
        accepted_age = await accept_betano_age_verification(page)
        closed_landing_modal = await close_betano_landing_modal(page)
    except Exception as exc:
        homepage_error = str(exc)

    if homepage_status in (403, 429):
        session_file_removed = await reset_betano_browser_state(page, context, session_path)
        try:
            await page.wait_for_timeout(random.randint(1500, 2500))
            homepage_response = await page.goto(homepage, wait_until="domcontentloaded", timeout=15000)
            homepage_retry_status = homepage_response.status if homepage_response else 0
            homepage_status = homepage_retry_status
            await page.wait_for_timeout(random.randint(2000, 3500))
            accepted_age = await accept_betano_age_verification(page)
            closed_landing_modal = await close_betano_landing_modal(page)
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
    football_click = await click_betano_football_from_homepage(page)

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
    closed_landing_modal = await close_betano_landing_modal(page) or closed_landing_modal

    # Incremental scroll also triggers lazy-loaded content.
    for scroll_y in (200, 450, 700):
        await page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        await page.wait_for_timeout(random.randint(300, 600))
    # Return to the POPULARES section before collecting league cards.
    await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    await page.wait_for_timeout(random.randint(400, 800))

    if session_path:
        try:
            Path(session_path).parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=session_path)
        except Exception:
            pass

    league_keywords = [
        "brasileir",
        "premier",
        "libertadores",
        "serie",
        "copa",
        "league",
        "bundesliga",
        "liga",
        "ligue",
        "championship",
        "sul-american",
        "feminino",
        "nbb",
        "la liga",
        "serie a",
        "eredivisie",
    ]

    all_clickables = page.locator(
        'div[role="button"], button, a[role="tab"], '
        '[class*="league"] div, [class*="pill"], [class*="chip"], [class*="tab-item"]'
    )
    clickable_count = await all_clickables.count()
    league_tabs = []
    for index in range(clickable_count):
        element = all_clickables.nth(index)
        try:
            text = (await element.inner_text(timeout=2000)).strip()
            if text and any(keyword in text.lower() for keyword in league_keywords):
                if len(text) < 60:
                    league_tabs.append((element, text))
        except Exception:
            continue

    seen_names: set[str] = set()
    unique_tabs = []
    for element, name in league_tabs:
        if name not in seen_names:
            seen_names.add(name)
            unique_tabs.append((element, name))
    league_tabs = unique_tabs

    leagues_to_scrape = min(len(league_tabs), max_leagues)
    if leagues_to_scrape == 0:
        extracted_at = datetime.now(timezone.utc).isoformat()
        records = await extract_betano_visible_matches(
            page=page,
            championship="Futebol - mercados populares",
            market_type="Resultado da partida",
            proxy=proxy,
            extracted_at=extracted_at,
        )
        if records:
            logger.info("Betano sem abas de liga; extraidos %s jogos da tela atual", len(records))
            return records
        visible_odds_count = await count_betano_visible_odds(page)
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

    records: list[ScrapedRecord] = []
    for tab_element, championship in league_tabs[:leagues_to_scrape]:
        extracted_at = datetime.now(timezone.utc).isoformat()

        try:
            await browser_paced_click(tab_element, page)
            await page.wait_for_timeout(random.randint(1500, 3500))

            records.extend(
                await extract_betano_visible_matches(
                    page=page,
                    championship=championship,
                    market_type="Resultado da partida",
                    proxy=proxy,
                    extracted_at=extracted_at,
                )
            )
        except Exception:
            continue

    return records
