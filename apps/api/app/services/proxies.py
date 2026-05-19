from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import ProxyProfile
from app.repositories import proxies as proxy_repository


def list_proxies(session: Session) -> list[ProxyProfile]:
    return proxy_repository.list_proxies(session)


def get_proxy_or_raise(session: Session, proxy_id: int) -> ProxyProfile:
    proxy = proxy_repository.get_proxy(session, proxy_id)
    if proxy is None:
        raise NotFoundError("proxy_not_found")
    return proxy


def enable_proxy(session: Session, proxy_id: int) -> ProxyProfile:
    proxy = get_proxy_or_raise(session, proxy_id)
    proxy.status = "active"
    proxy.cooldown_until = None
    session.commit()
    session.refresh(proxy)
    return proxy


def disable_proxy(session: Session, proxy_id: int) -> ProxyProfile:
    proxy = get_proxy_or_raise(session, proxy_id)
    proxy.status = "disabled"
    session.commit()
    session.refresh(proxy)
    return proxy


def cooldown_proxy(session: Session, proxy_id: int) -> ProxyProfile:
    proxy = get_proxy_or_raise(session, proxy_id)
    proxy.status = "cooldown"
    proxy.cooldown_until = datetime.utcnow() + timedelta(minutes=5)
    session.commit()
    session.refresh(proxy)
    return proxy
