from __future__ import annotations

import asyncio
import logging

from billiard.exceptions import SoftTimeLimitExceeded

from app.jobs.celery_app import celery_app
from app.jobs.events import add_event
from app.jobs.proxy_state import persist_proxy_state, sync_proxy_manager_from_db
from app.jobs.repository import (
    create_scheduled_job,
    load_job_for_processing,
    mark_job,
    replace_job_items,
    start_job_attempt,
)
from app.jobs.retry import handle_retryable_failure
from app.jobs.runtime import SessionLocal, make_captcha_provider, proxy_manager
from app.jobs.schedule import scheduled_scrape_jobs
from app.jobs.source_circuit import (
    ACTIVE_SOURCE_STATUS,
    CIRCUIT_OPEN_SOURCE_STATUS,
    refresh_source_circuit,
    source_unavailable_message,
)
from app.jobs.task_names import DEAD_LETTER_TASK, ENQUEUE_SCHEDULED_TASK, RUN_SCRAPE_TASK
from app.observability.metrics import (
    PROXY_ACTIVE_JOBS,
    PROXY_SELECTED,
    SCRAPE_ITEMS,
    SCRAPE_JOBS_BLOCKED,
    SCRAPE_JOBS_SUCCESS,
)
from app.proxy.policy import ensure_proxy_allowed
from app.resilience.host_policy import PolicyError
from app.scraping.contracts import LoginCredentials, ScrapeBlocked
from app.scraping.orchestrator import scrape_with_playwright
from app.settings import settings

logger = logging.getLogger(__name__)


@celery_app.task(name=ENQUEUE_SCHEDULED_TASK)
def enqueue_scheduled_scrape_jobs() -> dict:
    session = SessionLocal()
    scheduled_jobs = scheduled_scrape_jobs(
        interval_seconds=settings.scheduled_scrape_interval_seconds,
        protected_target_url=settings.scheduled_protected_target_url,
        books_to_scrape_url=settings.scheduled_books_to_scrape_url,
        globo_home_url=settings.scheduled_globo_home_url,
        betano_football_url=settings.scheduled_betano_football_url,
    )
    created_jobs: list[dict] = []
    skipped_sources: list[dict] = []
    try:
        for job_definition in scheduled_jobs:
            job_id = create_scheduled_job(session, job_definition)
            if job_id is None:
                skipped_sources.append({"source": job_definition["source"], "reason": "source_unavailable"})
                continue
            created_jobs.append({"job_id": job_id, "source": job_definition["source"]})
        session.commit()

        for job in created_jobs:
            celery_app.send_task(RUN_SCRAPE_TASK, args=[job["job_id"]], queue="scrape.jobs")

        return {"status": "scheduled", "jobs": created_jobs, "skipped_sources": skipped_sources}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(
    name=RUN_SCRAPE_TASK,
    bind=True,
    max_retries=max(0, settings.scraper_max_attempts - 1),
    soft_time_limit=max(1, settings.scraper_job_timeout_seconds - 10),
    time_limit=settings.scraper_job_timeout_seconds,
)
def run_scrape_job(self, job_id: int) -> dict:
    session = SessionLocal()
    proxy = None
    proxy_release_outcome = "success"
    try:
        job = load_job_for_processing(session, job_id)
        source_state = refresh_source_circuit(
            session,
            source_id=job["source_id"],
            status=job["source_status"],
            circuit_open_until=job["circuit_open_until"],
        )
        if source_state.closed_after_expiry:
            add_event(
                session,
                job_id,
                "source_circuit_closed",
                f"Circuito da fonte {job['source_name']} fechado apos cooldown",
                {"source": job["source_name"]},
            )
            session.commit()
        if source_state.status != ACTIVE_SOURCE_STATUS:
            message = source_unavailable_message(
                job["source_name"],
                source_state.status,
                source_state.circuit_open_until,
            )
            mark_job(session, job_id, "blocked_by_policy", error_message=message)
            add_event(
                session,
                job_id,
                "source_circuit_skipped" if source_state.status == CIRCUIT_OPEN_SOURCE_STATUS else "source_unavailable",
                message,
                {
                    "source": job["source_name"],
                    "source_status": source_state.status,
                    "circuit_open_until": (
                        source_state.circuit_open_until.isoformat()
                        if source_state.circuit_open_until
                        else None
                    ),
                },
            )
            session.commit()
            SCRAPE_JOBS_BLOCKED.inc()
            return {"status": "blocked_by_policy", "source_status": source_state.status}

        ensure_proxy_allowed(job["start_url"], settings.allowed_proxy_target_hosts)
        sync_proxy_manager_from_db(session, proxy_manager)
        attempt = start_job_attempt(session, job_id)
        add_event(
            session,
            job_id,
            "job_attempt_started",
            f"Tentativa {attempt} de {settings.scraper_max_attempts} iniciada",
            {"attempt": attempt, "max_attempts": settings.scraper_max_attempts},
        )
        session.commit()

        proxy = proxy_manager.select()
        PROXY_SELECTED.inc()
        PROXY_ACTIVE_JOBS.labels(proxy=proxy.name).set(proxy.current_active_jobs)
        add_event(session, job_id, "proxy_selected", f"Proxy {proxy.name} selecionado")
        persist_proxy_state(session, proxy)
        session.commit()

        records = asyncio.run(
            scrape_with_playwright(
                start_url=job["start_url"],
                max_pages=job["max_pages"],
                proxy=proxy,
                captcha_provider=make_captcha_provider(),
                login_credentials=LoginCredentials(
                    username=settings.target_site_username,
                    password=settings.target_site_password,
                ),
                page_timeout_seconds=settings.scraper_page_timeout_seconds,
                gbp_to_brl_rate=settings.gbp_to_brl_rate,
                media_root=settings.media_root,
                public_api_url=settings.public_api_url,
                globo_max_articles=settings.globo_max_articles,
                betano_max_leagues=settings.betano_max_leagues,
                betano_proxy_url=settings.betano_proxy_url,
                betano_debug_artifacts=settings.betano_debug_artifacts,
                betano_debug_max_artifacts=settings.betano_debug_max_artifacts,
            )
        )
        items_persisted = replace_job_items(session, job_id, records)
        mark_job(session, job_id, "success", items_found=items_persisted)
        add_event(
            session,
            job_id,
            "job_items_replaced",
            f"{items_persisted} itens persistidos de forma idempotente",
            {"items": items_persisted},
        )
        add_event(session, job_id, "job_success", f"{items_persisted} itens coletados")
        session.commit()
        SCRAPE_ITEMS.inc(items_persisted)
        SCRAPE_JOBS_SUCCESS.inc()
        return {"status": "success", "items": items_persisted}
    except ScrapeBlocked as exc:
        outcome = "rate_limited" if exc.status_code == 429 else "blocked"
        proxy_release_outcome = outcome
        SCRAPE_JOBS_BLOCKED.inc()
        return handle_retryable_failure(self, session, job_id, outcome, str(exc), exc)
    except PolicyError as exc:
        mark_job(session, job_id, "blocked_by_policy", error_message=str(exc))
        add_event(session, job_id, "blocked_by_policy", str(exc))
        session.commit()
        SCRAPE_JOBS_BLOCKED.inc()
        return {"status": "blocked_by_policy"}
    except SoftTimeLimitExceeded as exc:
        proxy_release_outcome = "rate_limited"
        return handle_retryable_failure(self, session, job_id, "timeout", "Tempo limite do job excedido", exc)
    except Exception as exc:
        proxy_release_outcome = "failed"
        return handle_retryable_failure(self, session, job_id, "failed", str(exc), exc)
    finally:
        if proxy:
            proxy_manager.release(proxy.name, proxy_release_outcome)
            PROXY_ACTIVE_JOBS.labels(proxy=proxy.name).set(proxy.current_active_jobs)
            try:
                persist_proxy_state(session, proxy)
                session.commit()
            except Exception as exc:
                session.rollback()
                logger.warning("falha_ao_sincronizar_proxy name=%s error=%s", proxy.name, exc)
        session.close()


@celery_app.task(name=DEAD_LETTER_TASK)
def dead_letter_scrape_job(payload: dict) -> dict:
    return payload
