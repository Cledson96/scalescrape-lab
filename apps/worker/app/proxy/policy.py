from app.resilience.host_policy import ensure_host_allowed


def ensure_proxy_allowed(target_url: str, allowed_hosts: set[str]) -> str:
    return ensure_host_allowed(target_url, allowed_hosts, "proxy_rotation")

