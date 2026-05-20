from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import Job, ScrapedItem, Source


def list_items(session: Session, job_id: int | None, limit: int) -> list[ScrapedItem]:
    query = select(ScrapedItem)
    if job_id is not None:
        query = query.where(ScrapedItem.job_id == job_id)
    query = query.order_by(desc(ScrapedItem.created_at)).limit(limit)
    return list(session.scalars(query))


def count_items_by_source(session: Session, source: str | None) -> int:
    query = select(func.count(ScrapedItem.id)).join(Job).join(Source)
    if source:
        query = query.where(Source.name == source)
    return session.scalar(query) or 0


def list_items_by_source(
    session: Session,
    source: str | None,
    page: int,
    page_size: int,
) -> list[ScrapedItem]:
    query = select(ScrapedItem).join(Job).join(Source)
    if source:
        query = query.where(Source.name == source)
    return list(
        session.scalars(
            query.order_by(desc(ScrapedItem.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )


def list_job_items(session: Session, job_id: int, limit: int) -> list[ScrapedItem]:
    query = (
        select(ScrapedItem)
        .where(ScrapedItem.job_id == job_id)
        .order_by(desc(ScrapedItem.created_at))
        .limit(limit)
    )
    return list(session.scalars(query))
