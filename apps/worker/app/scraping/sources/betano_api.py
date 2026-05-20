from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from urllib.parse import urljoin

from app.proxy.manager import ProxyProfileState
from app.scraping.contracts import ScrapedRecord, ScrapeBlocked
from app.scraping.runtime.debug_artifacts import (
    _message_with_debug_url,
    betano_block_message,
    maybe_save_betano_debug_artifacts,
)
from app.scraping.sources.betano_navigation import reset_betano_browser_state
from app.scraping.sources.betano_parser import build_betano_record_payload, extract_betano_external_id

BETANO_FOOTBALL_TODAY_API_PATH = "/api/sport/futebol/jogos-de-hoje/?req=s,stnf,c,mb,mbl"
logger = logging.getLogger(__name__)


def betano_football_today_api_url(football_url: str) -> str:
    base_url = football_url.split("/sport/")[0].rstrip("/")
    return f"{base_url}{BETANO_FOOTBALL_TODAY_API_PATH}"


def build_betano_api_records(
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


async def scrape_betano_football_api(
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
    await reset_betano_browser_state(page, context)
    api_url = betano_football_today_api_url(football_url)
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

    records = build_betano_api_records(
        payload=payload,
        proxy=proxy,
        max_leagues=max_leagues,
        base_url=football_url.split("/sport/")[0].rstrip("/") + "/",
        extracted_at=datetime.now(timezone.utc).isoformat(),
    )
    if records:
        logger.info("Betano API retornou %s jogos", len(records))
    return records


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
