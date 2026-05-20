from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import json
import logging
import re


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BetanoDebugArtifactPaths:
    metadata_path: str
    screenshot_path: str
    html_path: str
    metadata_url: str
    screenshot_url: str
    html_url: str


def mask_proxy_url(proxy_url: str | None) -> str:
    if not proxy_url:
        return "direct"
    parsed = urlsplit(proxy_url)
    if not parsed.username and not parsed.password:
        return proxy_url
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, f"***:***@{host}{port}", "", "", ""))


def betano_block_message(
    status_code: int,
    proxy_url: str | None,
    egress_ip: str | None = None,
    stage: str | None = None,
) -> str:
    details = [f"proxy={mask_proxy_url(proxy_url)}"]
    if egress_ip:
        details.append(f"egress_ip={egress_ip}")
    stage_text = f" durante {stage}" if stage else ""
    return f"bloqueio HTTP {status_code} no Betano{stage_text} ({', '.join(details)})"


def betano_no_league_tabs_message(clickable_count: int, odds_count: int, current_url: str) -> str:
    return (
        "Nenhuma aba de liga encontrada na secao POPULARES do Betano "
        f"(clickables={clickable_count}, odds={odds_count}, url={current_url})"
    )


def betano_debug_artifact_paths(
    *, media_root: str, stem: str, public_api_url: str = ""
) -> BetanoDebugArtifactPaths:
    safe_stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", stem).strip("-") or "betano-debug"
    local_base = Path(media_root) / "betano-debug" / safe_stem
    public_base = f"/media/betano-debug/{safe_stem}"

    def public_url(path: str) -> str:
        if not public_api_url:
            return path
        return f"{public_api_url.rstrip('/')}{path}"

    def local_path(path: Path) -> str:
        return str(path).replace("\\", "/")

    return BetanoDebugArtifactPaths(
        metadata_path=local_path(local_base.with_suffix(".json")),
        screenshot_path=local_path(local_base.with_suffix(".png")),
        html_path=local_path(local_base.with_suffix(".html")),
        metadata_url=public_url(f"{public_base}.json"),
        screenshot_url=public_url(f"{public_base}.png"),
        html_url=public_url(f"{public_base}.html"),
    )


def _message_with_debug_url(message: str, artifact: BetanoDebugArtifactPaths | None) -> str:
    if not artifact:
        return message
    return f"{message}; debug={artifact.metadata_url}"


def _cleanup_betano_debug_artifacts(media_root: str, max_artifacts: int) -> None:
    if max_artifacts <= 0:
        return
    debug_dir = Path(media_root) / "betano-debug"
    if not debug_dir.exists():
        return
    metadata_files = sorted(debug_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for metadata_file in metadata_files[max_artifacts:]:
        stem = metadata_file.with_suffix("")
        for path in (metadata_file, stem.with_suffix(".png"), stem.with_suffix(".html")):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                logger.debug("Nao foi possivel remover artefato antigo do Betano: %s", path)


async def save_betano_debug_artifacts(
    *,
    page,
    media_root: str,
    public_api_url: str,
    label: str,
    status_code: int | None,
    start_url: str,
    proxy_url: str | None,
    egress_ip: str | None,
    max_artifacts: int,
    context: dict | None = None,
) -> BetanoDebugArtifactPaths | None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    artifact = betano_debug_artifact_paths(
        media_root=media_root,
        stem=f"{timestamp}-{label}",
        public_api_url=public_api_url,
    )
    Path(artifact.metadata_path).parent.mkdir(parents=True, exist_ok=True)

    screenshot_error = None
    html_error = None
    page_title = ""
    page_url = ""
    body_excerpt = ""

    try:
        page_url = page.url
    except Exception:
        page_url = ""
    try:
        page_title = await page.title()
    except Exception:
        page_title = ""
    try:
        body_excerpt = (await page.locator("body").inner_text(timeout=2500)).strip()[:1500]
    except Exception:
        body_excerpt = ""
    try:
        await page.screenshot(path=artifact.screenshot_path, full_page=True)
    except Exception as exc:
        screenshot_error = str(exc)
    try:
        Path(artifact.html_path).write_text(await page.content(), encoding="utf-8")
    except Exception as exc:
        html_error = str(exc)

    metadata = {
        "label": label,
        "status_code": status_code,
        "start_url": start_url,
        "page_url": page_url,
        "title": page_title,
        "body_excerpt": body_excerpt,
        "proxy": mask_proxy_url(proxy_url),
        "egress_ip": egress_ip,
        "metadata_url": artifact.metadata_url,
        "screenshot_url": artifact.screenshot_url if screenshot_error is None else None,
        "html_url": artifact.html_url if html_error is None else None,
        "screenshot_error": screenshot_error,
        "html_error": html_error,
        "context": context or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    Path(artifact.metadata_path).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    _cleanup_betano_debug_artifacts(media_root, max_artifacts)
    logger.info("Betano debug salvo em %s", artifact.metadata_url)
    return artifact


async def maybe_save_betano_debug_artifacts(**kwargs) -> BetanoDebugArtifactPaths | None:
    try:
        return await save_betano_debug_artifacts(**kwargs)
    except Exception as exc:  # pragma: no cover - diagnostico nao deve derrubar o scraping
        logger.warning("Falha ao salvar debug do Betano: %s", exc)
        return None
