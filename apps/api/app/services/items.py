from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import ScrapedItem
from app.repositories import items as item_repository
from app.repositories import jobs as job_repository
from app.schemas import ScrapedItemPageRead


def list_items(session: Session, job_id: int | None, limit: int) -> list[ScrapedItem]:
    return item_repository.list_items(session, job_id, limit)


def list_items_page(
    session: Session,
    source: str | None,
    page: int,
    page_size: int,
) -> ScrapedItemPageRead:
    total = item_repository.count_items_by_source(session, source)
    items = item_repository.list_items_by_source(session, source, page, page_size)
    return ScrapedItemPageRead(items=items, total=total, page=page, page_size=page_size)


def list_job_items(session: Session, job_id: int, limit: int) -> list[ScrapedItem]:
    if job_repository.get_job(session, job_id) is None:
        raise NotFoundError("job_not_found")
    return item_repository.list_job_items(session, job_id, limit)
