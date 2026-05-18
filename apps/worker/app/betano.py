from __future__ import annotations

import hashlib
from datetime import datetime
from re import sub


def parse_betano_match_datetime(raw_text: str) -> dict:
    """Parse Betano date/time text like '19/05 15:30' or 'AO VIVO' into structured data.

    Returns a dict with:
        - date_str: the original date text (e.g. '19/05')
        - time_str: the original time text (e.g. '15:30')
        - is_live: whether the match is currently live
        - datetime_iso: ISO formatted datetime string (using current year) or empty if live
    """
    cleaned = raw_text.strip()

    if not cleaned:
        return {
            "date_str": "",
            "time_str": "",
            "is_live": False,
            "datetime_iso": "",
        }

    is_live = "ao vivo" in cleaned.lower()

    if is_live:
        return {
            "date_str": "Hoje",
            "time_str": "AO VIVO",
            "is_live": True,
            "datetime_iso": "",
        }

    # Format: "19/05 15:30" or "19/05 15:30 😀" (with possible trailing emojis/icons)
    parts = cleaned.split()
    date_str = parts[0] if len(parts) >= 1 else ""
    time_str = parts[1] if len(parts) >= 2 else ""

    datetime_iso = ""
    if date_str and time_str:
        try:
            current_year = datetime.now().year
            full_str = f"{date_str}/{current_year} {time_str}"
            parsed = datetime.strptime(full_str, "%d/%m/%Y %H:%M")
            datetime_iso = parsed.isoformat()
        except ValueError:
            pass

    return {
        "date_str": date_str,
        "time_str": time_str,
        "is_live": False,
        "datetime_iso": datetime_iso,
    }


def extract_betano_external_id(
    home_team: str,
    away_team: str,
    championship: str,
    match_datetime_raw: str,
) -> str:
    """Generate a deterministic external ID for a Betano match.

    Uses a hash of normalized team names, championship, and datetime
    to produce a stable, short identifier.
    """
    raw = f"{home_team}|{away_team}|{championship}|{match_datetime_raw}"
    normalized = sub(r"[^a-zA-Z0-9|]", "", raw.lower())
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    slug_home = sub(r"[^a-z0-9]+", "-", home_team.lower()).strip("-")[:20]
    slug_away = sub(r"[^a-z0-9]+", "-", away_team.lower()).strip("-")[:20]
    return f"betano-{slug_home}-vs-{slug_away}-{digest}"


def build_betano_record_payload(
    *,
    home_team: str,
    away_team: str,
    championship: str,
    market_type: str,
    odd_home: str,
    odd_draw: str,
    odd_away: str,
    match_datetime: dict,
    match_url: str,
    extracted_at: str,
) -> dict:
    """Build the raw_data payload for a Betano match record."""
    return {
        "source": "betano-football",
        "championship": championship,
        "home_team": home_team,
        "away_team": away_team,
        "market_type": market_type,
        "odds": {
            "home": _safe_float(odd_home),
            "draw": _safe_float(odd_draw),
            "away": _safe_float(odd_away),
            "home_raw": odd_home,
            "draw_raw": odd_draw,
            "away_raw": odd_away,
        },
        "match_date": match_datetime.get("date_str", ""),
        "match_time": match_datetime.get("time_str", ""),
        "match_datetime_iso": match_datetime.get("datetime_iso", ""),
        "is_live": match_datetime.get("is_live", False),
        "match_url": match_url,
        "extracted_at": extracted_at,
    }


def _safe_float(value: str) -> float:
    """Convert an odds string to float, returning 0.0 on failure."""
    try:
        return float(value.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0
