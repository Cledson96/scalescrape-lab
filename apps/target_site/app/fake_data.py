from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from math import ceil
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass(frozen=True)
class PublicRecord:
    external_id: str
    title: str
    category: str
    region: str
    status: str
    risk_score: int
    source_label: str
    raw_summary: str


@dataclass(frozen=True)
class RecordPage:
    records: list[PublicRecord]
    page_number: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


AREAS = [
    "mercado publico",
    "transacao sintetica",
    "catalogo municipal",
    "evento aberto",
    "inventario local",
    "cadastro operacional",
]

REGIONS = [
    "Curitiba PR",
    "Sao Paulo SP",
    "Belo Horizonte MG",
    "Florianopolis SC",
    "Porto Alegre RS",
    "Recife PE",
    "Goiania GO",
    "Fortaleza CE",
]

STATUSES = ["ativo", "em analise", "atualizado", "monitorado"]


def get_local_records(prefix: str = "normal", total: int = 240) -> list[PublicRecord]:
    return list(_build_local_records(prefix, total))


@lru_cache(maxsize=32)
def _build_local_records(prefix: str, total: int) -> tuple[PublicRecord, ...]:
    records = []
    safe_total = max(1, total)
    for index in range(1, safe_total + 1):
        area = AREAS[(index - 1) % len(AREAS)]
        region = REGIONS[(index * 3) % len(REGIONS)]
        status = STATUSES[(index * 5) % len(STATUSES)]
        risk_score = 12 + ((index * 17) % 79)
        records.append(
            PublicRecord(
                external_id=f"{prefix}-{index}",
                title=f"Registro publico {index:03d} - {area}",
                category=area,
                region=region,
                status=status,
                risk_score=risk_score,
                source_label="dataset local sintetico",
                raw_summary=(
                    f"fonte=local; lote={1 + ((index - 1) // 25)}; "
                    f"prioridade={1 + (index % 5)}; checksum={prefix}-{index * 37}"
                ),
            )
        )
    return tuple(records)


def paginate_records(records: list[PublicRecord], page_number: int, per_page: int = 12) -> RecordPage:
    safe_per_page = max(1, per_page)
    safe_page = max(1, page_number)
    total = len(records)
    total_pages = max(1, ceil(total / safe_per_page))
    if safe_page > total_pages:
        safe_page = total_pages
    start = (safe_page - 1) * safe_per_page
    end = start + safe_per_page
    return RecordPage(
        records=records[start:end],
        page_number=safe_page,
        per_page=safe_per_page,
        total=total,
        total_pages=total_pages,
        has_next=safe_page < total_pages,
        has_previous=safe_page > 1,
    )


def normalize_randomuser_payload(payload: dict, prefix: str = "external") -> list[PublicRecord]:
    normalized = []
    for index, item in enumerate(payload.get("results", []), start=1):
        location = item.get("location", {})
        dob = item.get("dob", {})
        timezone = location.get("timezone", {})
        country = location.get("country") or "pais sintetico"
        city = location.get("city") or "cidade sintetica"
        state = location.get("state") or "estado sintetico"
        nat = item.get("nat") or "ZZ"
        age = dob.get("age", "n/a")
        gender = item.get("gender", "n/a")
        normalized.append(
            PublicRecord(
                external_id=f"{prefix}-{index}",
                title=f"Registro sintetico {index:03d} - {country}",
                category=f"perfil sintetico {nat}",
                region=f"{city}, {state}, {country}",
                status="importado",
                risk_score=20 + ((index * 11) % 70),
                source_label="RandomUser fake API",
                raw_summary=(
                    f"fonte=randomuser; idade_aproximada={age}; genero={gender}; "
                    f"fuso={timezone.get('description', 'n/a')}"
                ),
            )
        )
    return normalized


def fetch_randomuser_records(size: int = 500, seed: str = "scalescrape-lab") -> list[PublicRecord]:
    safe_size = max(1, min(size, 5000))
    query = urlencode(
        {
            "results": safe_size,
            "seed": seed,
            "nat": "br,us,gb,es,fr",
            "noinfo": "",
        }
    )
    with urlopen(f"https://randomuser.me/api/?{query}", timeout=6) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return normalize_randomuser_payload(payload, prefix="external")


@lru_cache(maxsize=4)
def get_external_records(size: int = 500) -> tuple[PublicRecord, ...]:
    try:
        records = fetch_randomuser_records(size=size)
    except Exception:
        records = get_local_records(prefix="external-fallback", total=size)
    return tuple(records)


def find_record(record_id: str) -> PublicRecord | None:
    pools = [
        get_local_records(prefix="normal", total=240),
        get_local_records(prefix="protected", total=240),
        list(get_external_records(size=500)),
    ]
    for records in pools:
        for record in records:
            if record.external_id == record_id:
                return record
    return None
