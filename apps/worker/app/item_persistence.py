from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable, Protocol


class ScrapedRecordLike(Protocol):
    external_id: str
    title: str
    detail_url: str
    raw_data: dict


def build_scraped_item_rows(
    job_id: int,
    records: Iterable[ScrapedRecordLike],
    extracted_at: datetime | None = None,
) -> list[dict]:
    batch_extracted_at = extracted_at or datetime.utcnow()
    rows = []
    for record in records:
        raw_data = dict(record.raw_data)
        raw_data.setdefault("extracted_at", batch_extracted_at.isoformat())
        rows.append(
            {
                "job_id": job_id,
                "external_id": record.external_id,
                "title": record.title,
                "detail_url": record.detail_url,
                "raw_data": json.dumps(raw_data, ensure_ascii=False),
                "extracted_at": batch_extracted_at,
            }
        )
    return rows
