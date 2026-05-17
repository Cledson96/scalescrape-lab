from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProxyProfile, Source
from app.settings import get_settings


def seed_defaults(session: Session) -> None:
    settings = get_settings()
    source = session.scalar(
        select(Source).where(Source.name == settings.default_source_name)
    )
    if source is None:
        session.add(
            Source(
                name=settings.default_source_name,
                base_url=settings.default_source_url,
                status="active",
            )
        )

    for name in ("proxy-a", "proxy-b", "proxy-c"):
        proxy = session.scalar(select(ProxyProfile).where(ProxyProfile.name == name))
        if proxy is None:
            session.add(ProxyProfile(name=name, endpoint=f"lab://{name}"))

    session.commit()

