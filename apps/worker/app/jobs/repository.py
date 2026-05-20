from __future__ import annotations

import json

from sqlalchemy import text

from app.clock import utc_now_naive
from app.jobs.item_persistence import build_scraped_item_rows
from app.jobs.source_circuit import ACTIVE_SOURCE_STATUS, refresh_source_circuit

TERMINAL_JOB_STATUSES = {"success", "failed", "blocked", "rate_limited", "blocked_by_policy", "dead_lettered"}


def create_scheduled_job(session, job_definition: dict) -> int | None:
    session.execute(
        text(
            """
            insert into sources (name, base_url, status, created_at, updated_at)
            values (:source, :base_url, 'active', now(), now())
            on conflict (name) do update
            set base_url = excluded.base_url,
                updated_at = now()
            """
        ),
        {"source": job_definition["source"], "base_url": job_definition["start_url"]},
    )
    source = session.execute(
        text("select id, status, circuit_open_until from sources where name = :source"),
        {"source": job_definition["source"]},
    ).mappings().one()
    source_state = refresh_source_circuit(
        session,
        source_id=source["id"],
        status=source["status"],
        circuit_open_until=source["circuit_open_until"],
    )
    if source_state.status != ACTIVE_SOURCE_STATUS:
        return None
    job_id = session.execute(
        text(
            """
            insert into jobs (source_id, start_url, status, mode, max_pages, attempts, items_found, created_at, updated_at)
            values (:source_id, :start_url, 'pending', :mode, :max_pages, 0, 0, now(), now())
            returning id
            """
        ),
        {
            "source_id": source["id"],
            "start_url": job_definition["start_url"],
            "mode": job_definition["mode"],
            "max_pages": job_definition["max_pages"],
        },
    ).scalar_one()
    session.execute(
        text(
            """
            insert into job_events (job_id, event_type, message, metadata, created_at)
            values (:job_id, 'scheduled_job_created', :message, cast(:metadata as jsonb), now())
            """
        ),
        {
            "job_id": job_id,
            "message": "Job criado pelo agendador de scraping a cada 6 horas",
            "metadata": json.dumps(
                {
                    "source": job_definition["source"],
                    "interval_seconds": job_definition["interval_seconds"],
                }
            ),
        },
    )
    return int(job_id)


def load_job_for_processing(session, job_id: int):
    return session.execute(
        text(
            """
            select j.id, j.start_url, j.max_pages, j.source_id,
                   s.name as source_name, s.status as source_status, s.circuit_open_until
            from jobs j
            join sources s on s.id = j.source_id
            where j.id = :id
            """
        ),
        {"id": job_id},
    ).mappings().one()


def mark_job(session, job_id: int, status: str, error_message: str | None = None, items_found: int | None = None) -> None:
    updated_at = utc_now_naive()
    values = {
        "status": status,
        "error_message": error_message,
        "updated_at": updated_at,
        "finished_at": updated_at if status in TERMINAL_JOB_STATUSES else None,
        "job_id": job_id,
    }
    if items_found is None:
        session.execute(
            text(
                """
                update jobs
                set status = :status, error_message = :error_message, finished_at = :finished_at, updated_at = :updated_at
                where id = :job_id
                """
            ),
            values,
        )
    else:
        values["items_found"] = items_found
        session.execute(
            text(
                """
                update jobs
                set status = :status, error_message = :error_message, items_found = :items_found,
                    finished_at = now(), updated_at = :updated_at
                where id = :job_id
                """
            ),
            values,
        )


def start_job_attempt(session, job_id: int) -> int:
    return int(
        session.execute(
            text(
                """
                update jobs
                set status = 'running', attempts = attempts + 1, started_at = coalesce(started_at, now()),
                    finished_at = null, updated_at = now()
                where id = :job_id
                returning attempts
                """
            ),
            {"job_id": job_id},
        ).scalar_one()
    )


def replace_job_items(session, job_id: int, records) -> int:
    rows = build_scraped_item_rows(job_id, records)
    session.execute(text("delete from scraped_items where job_id = :job_id"), {"job_id": job_id})
    for row in rows:
        session.execute(
            text(
                """
                insert into scraped_items (job_id, external_id, title, detail_url, raw_data, created_at)
                values (:job_id, :external_id, :title, :detail_url, cast(:raw_data as jsonb), :extracted_at)
                """
            ),
            row,
        )
    return len(rows)


def get_job_attempt(session, job_id: int) -> int:
    return int(
        session.execute(
            text("select attempts from jobs where id = :job_id"),
            {"job_id": job_id},
        ).scalar_one()
    )
