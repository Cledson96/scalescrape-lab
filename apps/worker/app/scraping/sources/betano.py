from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import json
import logging
import random
import re

from app.scraping.sources.betano_parser import (
    build_betano_record_payload,
    extract_betano_external_id,
    parse_betano_match_datetime,
)
from app.scraping.runtime.debug_artifacts import (
    _message_with_debug_url,
    betano_block_message,
    betano_no_league_tabs_message,
    maybe_save_betano_debug_artifacts,
)
from app.proxy.manager import ProxyProfileState
from app.scraping.contracts import ScrapedRecord, ScrapeBlocked


BETANO_HOST = "www.betano.bet.br"
BETANO_FOOTBALL_TODAY_API_PATH = "/api/sport/futebol/jogos-de-hoje/?req=s,stnf,c,mb,mbl"
logger = logging.getLogger(__name__)


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
