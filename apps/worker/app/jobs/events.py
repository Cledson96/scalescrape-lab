from __future__ import annotations

import json

from sqlalchemy import text


def add_event(session, job_id: int, event_type: str, message: str, metadata: dict | None = None) -> None:
    session.execute(
        text(
            """
            insert into job_events (job_id, event_type, message, metadata, created_at)
            values (:job_id, :event_type, :message, cast(:metadata as jsonb), now())
            """
        ),
        {
            "job_id": job_id,
            "event_type": event_type,
            "message": message,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
        },
    )
