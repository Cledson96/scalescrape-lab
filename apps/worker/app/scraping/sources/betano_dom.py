from __future__ import annotations

import re

from app.proxy.manager import ProxyProfileState
from app.scraping.contracts import ScrapedRecord
from app.scraping.sources.betano_parser import (
    build_betano_record_payload,
    extract_betano_external_id,
    parse_betano_match_datetime,
)


async def count_betano_visible_odds(page) -> int:  # noqa: ANN001
    buttons = await _betano_visible_odd_buttons(page)
    return len(buttons)


async def extract_betano_visible_matches(
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


async def _betano_visible_odd_buttons(page) -> list:  # noqa: ANN001
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
    """Build a ScrapedRecord from a group of 3 odds buttons (1/X/2)."""
    odd_home = (await btn_home.inner_text()).strip()
    odd_draw = (await btn_draw.inner_text()).strip()
    odd_away = (await btn_away.inner_text()).strip()

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
    lines = [line.strip() for line in parent_text.split("\n") if line.strip()]

    home_team = ""
    away_team = ""
    match_datetime_raw = ""
    match_url = ""

    match_link = parent.locator("a[href*='/odds/']")
    if await match_link.count() > 0:
        match_url = await match_link.first.get_attribute("href") or ""

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
        if any(
            keyword in line.lower()
            for keyword in [
                "resultado",
                "mais/menos",
                "ambos",
                "chance",
                "escanteios",
                "intervalo",
                "visitar",
                "populares",
                "empate",
                "dupla",
            ]
        ):
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
    external_id = extract_betano_external_id(home_team, away_team, championship, match_datetime_raw)
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
    return ScrapedRecord(
        external_id=external_id,
        title=f"{home_team} vs {away_team}",
        detail_url=match_url,
        raw_data={**payload, "proxy": proxy.name},
    )
