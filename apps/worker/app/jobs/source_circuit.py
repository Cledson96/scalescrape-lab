from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from app.jobs.events import add_event
from app.resilience.source_circuit import (
    ACTIVE_SOURCE_STATUS,
    CIRCUIT_OPEN_SOURCE_STATUS,
    next_source_circuit_deadline,
    normalize_source_circuit,
    should_open_source_circuit,
)
from app.settings import settings


def refresh_source_circuit(session, source_id: int, status: str, circuit_open_until: datetime | None):
    state = normalize_source_circuit(status, circuit_open_until)
    if state.closed_after_expiry:
        session.execute(
            text(
                """
                update sources
                set status = 'active', circuit_open_until = null, updated_at = now()
                where id = :source_id
                """
            ),
            {"source_id": source_id},
        )
    return state


def source_unavailable_message(source_name: str, status: str, circuit_open_until: datetime | None) -> str:
    if status == CIRCUIT_OPEN_SOURCE_STATUS:
        until = circuit_open_until.isoformat() if circuit_open_until else "indefinido"
        return f"Fonte {source_name} com circuito aberto ate {until}"
    return f"Fonte {source_name} indisponivel para execucao: {status}"


def maybe_open_source_circuit(session, job_id: int, outcome: str) -> None:
    source = session.execute(
        text(
            """
            select s.id, s.name, s.status, s.circuit_open_until
            from sources s
            join jobs j on j.source_id = s.id
            where j.id = :job_id
            """
        ),
        {"job_id": job_id},
    ).mappings().one()
    if source["status"] not in {ACTIVE_SOURCE_STATUS, CIRCUIT_OPEN_SOURCE_STATUS}:
        return

    recent_outcomes = recent_source_failure_outcomes(
        session,
        job_id,
        limit=settings.source_circuit_failure_threshold,
    )
    if not should_open_source_circuit(recent_outcomes, settings.source_circuit_failure_threshold):
        return

    deadline = next_source_circuit_deadline(settings.source_circuit_cooldown_seconds)
    session.execute(
        text(
            """
            update sources
            set status = 'circuit_open', circuit_open_until = :circuit_open_until, updated_at = now()
            where id = :source_id
            """
        ),
        {"source_id": source["id"], "circuit_open_until": deadline},
    )
    add_event(
        session,
        job_id,
        "source_circuit_opened",
        (
            f"Circuito da fonte {source['name']} aberto por "
            f"{settings.source_circuit_cooldown_seconds}s apos falhas consecutivas"
        ),
        {
            "source": source["name"],
            "outcome": outcome,
            "recent_outcomes": recent_outcomes,
            "failure_threshold": settings.source_circuit_failure_threshold,
            "circuit_open_until": deadline.isoformat(),
        },
    )


def recent_source_failure_outcomes(session, job_id: int, limit: int) -> list[str]:
    rows = session.execute(
        text(
            """
            select case
                     when e.event_type = 'job_success' then 'success'
                     else e.metadata->>'outcome'
                   end as outcome
            from job_events e
            join jobs event_job on event_job.id = e.job_id
            join jobs current_job on current_job.source_id = event_job.source_id
            where current_job.id = :job_id
              and e.event_type in ('job_retry_scheduled', 'job_dead_lettered', 'job_success')
            order by e.created_at desc
            limit :limit
            """
        ),
        {"job_id": job_id, "limit": max(1, limit)},
    )
    return [row.outcome for row in rows if row.outcome]
