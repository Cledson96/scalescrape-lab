from __future__ import annotations

import asyncio
import json
from datetime import datetime
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
    SCRAPE_JOBS_FAILED,
    SCRAPE_JOBS_SUCCESS,
)
from app.policy import PolicyError
from app.proxy.manager import default_proxy_manager
from app.proxy.policy import ensure_proxy_allowed
from app.schedule import scheduled_scrape_jobs
from app.scraper import LoginCredentials, ScrapeBlocked, scrape_with_playwright
from app.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
proxy_manager = default_proxy_manager()


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


@celery_app.task(name="app.tasks.run_scrape_job", bind=True, max_retries=3)
def run_scrape_job(self, job_id: int) -> dict:
    session = SessionLocal()
    proxy = None
    try:
        job = session.execute(
            text("select id, start_url, max_pages from jobs where id = :id"),
            {"id": job_id},
        ).mappings().one()
        ensure_proxy_allowed(job["start_url"], settings.allowed_proxy_target_hosts)
        proxy = proxy_manager.select()
        PROXY_SELECTED.inc()
        PROXY_ACTIVE_JOBS.labels(proxy=proxy.name).set(proxy.current_active_jobs)
        mark_job(session, job_id, "running")
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
                globo_max_articles=settings.globo_max_articles,
                betano_max_leagues=settings.betano_max_leagues,
                betano_proxy_url=settings.betano_proxy_url,
            )
        )
        for record in records:
            extracted_at = datetime.utcnow()
            raw_data = dict(record.raw_data)
            raw_data.setdefault("extracted_at", extracted_at.isoformat())
            session.execute(
                text(
                    """
                    insert into scraped_items (job_id, external_id, title, detail_url, raw_data, created_at)
                    values (:job_id, :external_id, :title, :detail_url, cast(:raw_data as jsonb), :extracted_at)
                    """
                ),
                {
                    "job_id": job_id,
                    "external_id": record.external_id,
                    "title": record.title,
                    "detail_url": record.detail_url,
                    "raw_data": json.dumps(raw_data, ensure_ascii=False),
                    "extracted_at": extracted_at,
                },
            )
        mark_job(session, job_id, "success", items_found=len(records))
        add_event(session, job_id, "job_success", f"{len(records)} itens coletados")
        session.commit()
        SCRAPE_ITEMS.inc(len(records))
        SCRAPE_JOBS_SUCCESS.inc()
        return {"status": "success", "items": len(records)}
    except ScrapeBlocked as exc:
        outcome = "rate_limited" if exc.status_code == 429 else "blocked"
        mark_job(session, job_id, outcome, error_message=str(exc))
        add_event(session, job_id, outcome, str(exc))
        session.commit()
        SCRAPE_JOBS_BLOCKED.inc()
        if proxy:
            proxy_manager.release(proxy.name, "rate_limited" if exc.status_code == 429 else "blocked")
        raise self.retry(exc=exc, countdown=30)
    except PolicyError as exc:
        mark_job(session, job_id, "blocked_by_policy", error_message=str(exc))
        add_event(session, job_id, "blocked_by_policy", str(exc))
        session.commit()
        SCRAPE_JOBS_BLOCKED.inc()
        return {"status": "blocked_by_policy"}
    except Exception as exc:
        mark_job(session, job_id, "failed", error_message=str(exc))
        add_event(session, job_id, "job_failed", str(exc))
        session.commit()
        SCRAPE_JOBS_FAILED.inc()
        raise
    finally:
        if proxy:
            proxy_manager.release(proxy.name)
            PROXY_ACTIVE_JOBS.labels(proxy=proxy.name).set(proxy.current_active_jobs)
        session.close()


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
    values = {
        "status": status,
        "error_message": error_message,
        "updated_at": datetime.utcnow(),
        "job_id": job_id,
    }
    if items_found is None:
        session.execute(
            text(
                """
                update jobs set status = :status, error_message = :error_message, updated_at = :updated_at
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


def add_event(session, job_id: int, event_type: str, message: str) -> None:
    session.execute(
        text(
            """
            insert into job_events (job_id, event_type, message, metadata, created_at)
            values (:job_id, :event_type, :message, '{}'::jsonb, now())
            """
        ),
        {"job_id": job_id, "event_type": event_type, "message": message},
    )

