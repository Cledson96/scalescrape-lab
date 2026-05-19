from __future__ import annotations

import asyncio
import json
from datetime import datetime
from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.captcha.mock_provider import MockCaptchaResolverProvider
from app.captcha.two_captcha_provider import TwoCaptchaConfig, TwoCaptchaImageResolverProvider
from app.celery_app import celery_app
from app.metrics import (
    PROXY_ACTIVE_JOBS,
    PROXY_SELECTED,
    SCRAPE_ITEMS,
    SCRAPE_JOBS_BLOCKED,
    SCRAPE_JOBS_DEAD_LETTER,
    SCRAPE_JOBS_FAILED,
    SCRAPE_JOBS_SUCCESS,
)
from app.item_persistence import build_scraped_item_rows
from app.policy import PolicyError
from app.proxy.manager import default_proxy_manager
from app.proxy.policy import ensure_proxy_allowed
from app.retry_policy import retry_countdown_seconds, status_after_retryable_failure
from app.schedule import scheduled_scrape_jobs
from app.scraper import LoginCredentials, ScrapeBlocked, scrape_with_playwright
from app.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
proxy_manager = default_proxy_manager()
TERMINAL_JOB_STATUSES = {"success", "failed", "blocked", "rate_limited", "blocked_by_policy", "dead_lettered"}


def make_captcha_provider():
    if settings.enable_real_2captcha:
        return TwoCaptchaImageResolverProvider(
            TwoCaptchaConfig(
                api_key=settings.two_captcha_api_key,
                allowed_hosts=settings.allowed_captcha_hosts,
                enabled=True,
                max_solves_per_run=settings.max_captcha_solves_per_run,
            )
        )
    return MockCaptchaResolverProvider()


@celery_app.task(name="app.tasks.enqueue_scheduled_scrape_jobs")
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
    try:
        for job_definition in scheduled_jobs:
            job_id = create_scheduled_job(session, job_definition)
            created_jobs.append({"job_id": job_id, "source": job_definition["source"]})
        session.commit()

        for job in created_jobs:
            celery_app.send_task("app.tasks.run_scrape_job", args=[job["job_id"]], queue="scrape.jobs")

        return {"status": "scheduled", "jobs": created_jobs}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(
    name="app.tasks.run_scrape_job",
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
        job = session.execute(
            text("select id, start_url, max_pages from jobs where id = :id"),
            {"id": job_id},
        ).mappings().one()
        ensure_proxy_allowed(job["start_url"], settings.allowed_proxy_target_hosts)
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
        session.close()


@celery_app.task(name="app.tasks.dead_letter_scrape_job")
def dead_letter_scrape_job(payload: dict) -> dict:
    return payload


def create_scheduled_job(session, job_definition: dict) -> int:
    session.execute(
        text(
            """
            insert into sources (name, base_url, status, created_at, updated_at)
            values (:source, :base_url, 'active', now(), now())
            on conflict (name) do update
            set base_url = excluded.base_url,
                status = 'active',
                updated_at = now()
            """
        ),
        {"source": job_definition["source"], "base_url": job_definition["start_url"]},
    )
    source_id = session.execute(
        text("select id from sources where name = :source"),
        {"source": job_definition["source"]},
    ).scalar_one()
    job_id = session.execute(
        text(
            """
            insert into jobs (source_id, start_url, status, mode, max_pages, attempts, items_found, created_at, updated_at)
            values (:source_id, :start_url, 'pending', :mode, :max_pages, 0, 0, now(), now())
            returning id
            """
        ),
        {
            "source_id": source_id,
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


def mark_job(session, job_id: int, status: str, error_message: str | None = None, items_found: int | None = None) -> None:
    updated_at = datetime.utcnow()
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


def handle_retryable_failure(self, session, job_id: int, outcome: str, message: str, exc: Exception) -> dict:
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
            {"attempt": attempt, "max_attempts": settings.scraper_max_attempts, "countdown_seconds": countdown, "outcome": outcome},
        )
        session.commit()
        raise self.retry(exc=exc, countdown=countdown, max_retries=max(0, settings.scraper_max_attempts - 1), queue="scrape.retry")

    mark_job(session, job_id, next_status, error_message=message)
    add_event(
        session,
        job_id,
        "job_dead_lettered",
        f"Job enviado para DLQ apos {attempt} tentativa(s): {outcome}",
        {"attempt": attempt, "max_attempts": settings.scraper_max_attempts, "outcome": outcome},
    )
    session.commit()
    SCRAPE_JOBS_FAILED.inc()
    SCRAPE_JOBS_DEAD_LETTER.inc()
    celery_app.send_task(
        "app.tasks.dead_letter_scrape_job",
        kwargs={"payload": {"job_id": job_id, "outcome": outcome, "attempt": attempt, "message": message}},
        queue="scrape.dead_letter",
    )
    return {"status": next_status, "outcome": outcome, "attempt": attempt}


def get_job_attempt(session, job_id: int) -> int:
    return int(session.execute(text("select attempts from jobs where id = :job_id"), {"job_id": job_id}).scalar_one())


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

