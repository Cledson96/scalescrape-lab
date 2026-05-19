from __future__ import annotations

from sqlalchemy import text

from app.proxy.manager import ProxyProfileState, ProxyManager, proxy_states_from_rows
from app.settings import settings


def sync_proxy_manager_from_db(session, manager: ProxyManager) -> None:
    if not settings.enable_proxy_rotation:
        return
    rows = session.execute(
        text(
            """
            select name, status, current_active_jobs, max_concurrent_jobs,
                   blocked_count, rate_limited_count, cooldown_until
            from proxy_profiles
            order by name
            """
        )
    ).mappings().all()
    manager.sync(proxy_states_from_rows(rows))


def persist_proxy_state(session, proxy: ProxyProfileState) -> None:
    if not settings.enable_proxy_rotation or proxy.name == "direct":
        return
    session.execute(
        text(
            """
            update proxy_profiles
            set status = :status,
                current_active_jobs = :current_active_jobs,
                blocked_count = :blocked_count,
                rate_limited_count = :rate_limited_count,
                cooldown_until = :cooldown_until,
                updated_at = now()
            where name = :name
            """
        ),
        {
            "name": proxy.name,
            "status": proxy.status,
            "current_active_jobs": proxy.current_active_jobs,
            "blocked_count": proxy.blocked_count,
            "rate_limited_count": proxy.rate_limited_count,
            "cooldown_until": proxy.cooldown_until,
        },
    )
