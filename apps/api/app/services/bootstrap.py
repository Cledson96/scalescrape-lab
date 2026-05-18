from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProxyProfile, Source
from app.settings import get_settings


def seed_defaults(session: Session) -> None:
    settings = get_settings()
    sources = {
        settings.default_source_name: settings.default_source_url,
        "books-to-scrape": "https://books.toscrape.com/catalogue/category/books/science-fiction_16/index.html",
    }
    for name, base_url in sources.items():
        source = session.scalar(select(Source).where(Source.name == name))
        if source is None:
            session.add(Source(name=name, base_url=base_url, status="active"))

    for name in ("proxy-a", "proxy-b", "proxy-c"):
        proxy = session.scalar(select(ProxyProfile).where(ProxyProfile.name == name))
        if proxy is None:
            session.add(ProxyProfile(name=name, endpoint=f"lab://{name}"))

    session.commit()

