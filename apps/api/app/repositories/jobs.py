from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Job


def get_job(session: Session, job_id: int) -> Job | None:
    return session.get(Job, job_id)


def list_recent_jobs(session: Session, limit: int = 100) -> list[Job]:
    return list(session.scalars(select(Job).order_by(desc(Job.created_at)).limit(limit)))
