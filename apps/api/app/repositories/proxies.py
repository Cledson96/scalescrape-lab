from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProxyProfile


def get_proxy(session: Session, proxy_id: int) -> ProxyProfile | None:
    return session.get(ProxyProfile, proxy_id)


def list_proxies(session: Session) -> list[ProxyProfile]:
    return list(session.scalars(select(ProxyProfile).order_by(ProxyProfile.name)))
