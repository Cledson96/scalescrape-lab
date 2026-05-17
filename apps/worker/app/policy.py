from urllib.parse import urlparse


class PolicyError(RuntimeError):
    pass


def host_from_url(url: str) -> str:
    host = urlparse(url).hostname
    if not host:
        raise PolicyError(f"URL sem host valido: {url}")
    return host


def ensure_host_allowed(url_or_host: str, allowed_hosts: set[str], action: str) -> str:
    host = host_from_url(url_or_host) if "://" in url_or_host else url_or_host
    if host not in allowed_hosts:
        raise PolicyError(f"{action} bloqueado por policy para host: {host}")
    return host

