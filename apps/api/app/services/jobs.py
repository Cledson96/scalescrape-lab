from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.metrics import SCRAPE_JOBS_TOTAL
from app.models import Job, JobEvent
from app.repositories import jobs as job_repository
from app.repositories import sources as source_repository
from app.schemas import JobCreate
from app.services.queue import enqueue_scrape_job
from app.services.sources import ensure_source_available


def create_scrape_job(session: Session, payload: JobCreate) -> Job:
    source = source_repository.get_source_by_name(session, payload.source)
    if source is None:
        raise NotFoundError("source_not_found")
    ensure_source_available(session, source)

    job = Job(
        source_id=source.id,
        start_url=payload.start_url,
        mode=payload.mode,
        max_pages=payload.max_pages,
        status="pending",
    )
    session.add(job)
    session.flush()
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="job_created",
            message="Job criado pela API",
            metadata_json={"source": payload.source},
        )
    )
    session.commit()
    session.refresh(job)
    SCRAPE_JOBS_TOTAL.inc()
    enqueue_scrape_job(job.id)
    return job


def list_recent_jobs(session: Session) -> list[Job]:
    return job_repository.list_recent_jobs(session)


def get_job(session: Session, job_id: int) -> Job:
    job = job_repository.get_job(session, job_id)
    if job is None:
        raise NotFoundError("job_not_found")
    return job


def retry_scrape_job(session: Session, job_id: int) -> Job:
    job = get_job(session, job_id)
    ensure_source_available(session, job.source)
    job.status = "pending"
    job.attempts = 0
    job.error_message = None
    job.finished_at = None
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="job_retry_requested",
            message="Retry manual solicitado",
        )
    )
    session.commit()
    enqueue_scrape_job(job.id)
    return job
