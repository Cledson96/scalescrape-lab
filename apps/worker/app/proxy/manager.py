from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from scalescrape_contracts.clock import utc_now_naive


@dataclass
class ProxyProfileState:
    name: str
    status: str = "active"
    current_active_jobs: int = 0
    max_concurrent_jobs: int = 3
    blocked_count: int = 0
    rate_limited_count: int = 0
    cooldown_until: datetime | None = None

    def available(self, now: datetime | None = None) -> bool:
        current = now or utc_now_naive()
        if self.status == "cooldown" and self.cooldown_until and self.cooldown_until <= current:
            self.status = "active"
            self.cooldown_until = None
        return self.status == "active" and self.current_active_jobs < self.max_concurrent_jobs


class ProxyManager:
    def __init__(self, proxies: list[ProxyProfileState], cooldown_seconds: int = 300) -> None:
        self.proxies = proxies
        self.cooldown_seconds = cooldown_seconds

    def select(self) -> ProxyProfileState:
        candidates = [proxy for proxy in self.proxies if proxy.available()]
        if not candidates:
            raise RuntimeError("nenhum proxy disponivel")
        selected = sorted(candidates, key=lambda proxy: proxy.current_active_jobs)[0]
        selected.current_active_jobs += 1
        return selected

    def release(self, proxy_name: str, outcome: str = "success") -> None:
        proxy = self._get(proxy_name)
        proxy.current_active_jobs = max(0, proxy.current_active_jobs - 1)
        if outcome == "blocked":
            proxy.blocked_count += 1
        if outcome == "rate_limited":
            proxy.rate_limited_count += 1
        if proxy.blocked_count >= 2 or proxy.rate_limited_count >= 3:
            proxy.status = "cooldown"
            proxy.cooldown_until = utc_now_naive() + timedelta(seconds=self.cooldown_seconds)

    def sync(self, proxies: list[ProxyProfileState]) -> None:
        if proxies:
            self.proxies = proxies

    def _get(self, proxy_name: str) -> ProxyProfileState:
        for proxy in self.proxies:
            if proxy.name == proxy_name:
                return proxy
        raise KeyError(proxy_name)


def default_proxy_manager(
    *,
    max_concurrent_jobs: int = 3,
    cooldown_seconds: int = 300,
    enable_rotation: bool = True,
) -> ProxyManager:
    if not enable_rotation:
        return ProxyManager(
            [ProxyProfileState("direct", max_concurrent_jobs=max_concurrent_jobs)],
            cooldown_seconds=cooldown_seconds,
        )
    return ProxyManager(
        [
            ProxyProfileState("proxy-a", max_concurrent_jobs=max_concurrent_jobs),
            ProxyProfileState("proxy-b", max_concurrent_jobs=max_concurrent_jobs),
            ProxyProfileState("proxy-c", max_concurrent_jobs=max_concurrent_jobs),
        ],
        cooldown_seconds=cooldown_seconds,
    )


def proxy_state_from_mapping(row: Mapping[str, Any]) -> ProxyProfileState:
    return ProxyProfileState(
        name=str(row["name"]),
        status=str(row.get("status") or "active"),
        current_active_jobs=int(row.get("current_active_jobs") or 0),
        max_concurrent_jobs=int(row.get("max_concurrent_jobs") or 3),
        blocked_count=int(row.get("blocked_count") or 0),
        rate_limited_count=int(row.get("rate_limited_count") or 0),
        cooldown_until=row.get("cooldown_until"),
    )


def proxy_states_from_rows(rows: Iterable[Mapping[str, Any]]) -> list[ProxyProfileState]:
    return [proxy_state_from_mapping(row) for row in rows]
