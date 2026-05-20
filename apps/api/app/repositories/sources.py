from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Source


def get_source(session: Session, source_id: int) -> Source | None:
    return session.get(Source, source_id)


def get_source_by_name(session: Session, name: str) -> Source | None:
    return session.scalar(select(Source).where(Source.name == name))


def list_sources(session: Session) -> list[Source]:
    return list(session.scalars(select(Source).order_by(Source.name)))
