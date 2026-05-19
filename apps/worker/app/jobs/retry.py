from __future__ import annotations

from app.jobs.celery_app import celery_app
from app.jobs.events import add_event
from app.jobs.repository import get_job_attempt, mark_job
from app.jobs.source_circuit import maybe_open_source_circuit
from app.jobs.task_names import DEAD_LETTER_TASK
from app.observability.metrics import SCRAPE_JOBS_DEAD_LETTER, SCRAPE_JOBS_FAILED
from app.resilience.retry_policy import retry_countdown_seconds, status_after_retryable_failure
from app.settings import settings


def handle_retryable_failure(task, session, job_id: int, outcome: str, message: str, exc: Exception) -> dict:
    attempt = get_job_attempt(session, job_id)
    next_status = status_after_retryable_failure(outcome, attempt, settings.scraper_max_attempts)
    if next_status == "retrying":
        countdown = retry_countdown_seconds(attempt)
        mark_job(session, job_id, "retrying", error_message=message)
        add_event(
            session,
            job_id,
            "job_retry_scheduled",
            f"Retry agendado em {countdown}s apos {outcome}",
            {
                "attempt": attempt,
                "max_attempts": settings.scraper_max_attempts,
                "countdown_seconds": countdown,
                "outcome": outcome,
            },
        )
        maybe_open_source_circuit(session, job_id, outcome)
        session.commit()
        raise task.retry(
            exc=exc,
            countdown=countdown,
            max_retries=max(0, settings.scraper_max_attempts - 1),
            queue="scrape.retry",
        )

    mark_job(session, job_id, next_status, error_message=message)
    add_event(
        session,
        job_id,
        "job_dead_lettered",
        f"Job enviado para DLQ apos {attempt} tentativa(s): {outcome}",
        {"attempt": attempt, "max_attempts": settings.scraper_max_attempts, "outcome": outcome},
    )
    maybe_open_source_circuit(session, job_id, outcome)
    session.commit()
    SCRAPE_JOBS_FAILED.inc()
    SCRAPE_JOBS_DEAD_LETTER.inc()
    celery_app.send_task(
        DEAD_LETTER_TASK,
        kwargs={
            "payload": {
                "job_id": job_id,
                "outcome": outcome,
                "attempt": attempt,
                "message": message,
            }
        },
        queue="scrape.dead_letter",
    )
    return {"status": next_status, "outcome": outcome, "attempt": attempt}
