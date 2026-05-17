from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


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
        current = now or datetime.now(timezone.utc).replace(tzinfo=None)
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
            proxy.cooldown_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
                seconds=self.cooldown_seconds
            )

    def _get(self, proxy_name: str) -> ProxyProfileState:
        for proxy in self.proxies:
            if proxy.name == proxy_name:
                return proxy
        raise KeyError(proxy_name)


def default_proxy_manager(max_concurrent_jobs: int = 3) -> ProxyManager:
    return ProxyManager(
        [
            ProxyProfileState("proxy-a", max_concurrent_jobs=max_concurrent_jobs),
            ProxyProfileState("proxy-b", max_concurrent_jobs=max_concurrent_jobs),
            ProxyProfileState("proxy-c", max_concurrent_jobs=max_concurrent_jobs),
        ]
    )
