from __future__ import annotations

from html import unescape
from pathlib import Path
from re import DOTALL, IGNORECASE, finditer, search, sub
from urllib.parse import urljoin, urlparse


ALLOWED_GLOBO_ARTICLE_HOSTS = {
    "cbn.globo.com",
    "epocanegocios.globo.com",
    "g1.globo.com",
    "ge.globo.com",
    "gshow.globo.com",
    "globorural.globo.com",
    "oglobo.globo.com",
    "receitas.globo.com",
    "revistacasaejardim.globo.com",
    "revistacrescer.globo.com",
    "revistagalileu.globo.com",
    "revistamarieclaire.globo.com",
    "revistamonet.globo.com",
    "revistaquem.globo.com",
    "valor.globo.com",
}


def strip_tags(value: str) -> str:
    return " ".join(unescape(sub(r"<[^>]+>", " ", value)).split())


def attr_value(tag: str, name: str) -> str:
    match = search(rf'\b{name}=["\']([^"\']+)["\']', tag)
    return unescape(match.group(1)).strip() if match else ""


def is_allowed_globo_article_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.netloc.lower() in ALLOWED_GLOBO_ARTICLE_HOSTS
        and parsed.path.endswith(".ghtml")
    )


def is_allowed_globo_image_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return parsed.scheme in {"http", "https"} and (host == "glbimg.com" or host.endswith(".glbimg.com"))


def category_for_link(preceding_html: str, detail_url: str) -> str:
    matches = list(finditer(r'data-tracking-action=["\']([^"\']+)["\']', preceding_html))
    if matches:
        category = unescape(matches[-1].group(1)).split("|")[0].strip()
        if category:
            return category

    host = urlparse(detail_url).netloc.lower()
    if host == "ge.globo.com":
        return "esporte"
    if host == "gshow.globo.com":
        return "entretenimento"
    if host == "valor.globo.com":
        return "economia"
    return "jornalismo"


def parse_globo_home_cards(html: str, *, base_url: str, max_articles: int = 12) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    seen: set[str] = set()

    pattern = r'(<a\b[^>]*class=["\'][^"\']*post__link[^"\']*["\'][^>]*>)(?P<body>.*?)</a>'
    for match in finditer(pattern, html, flags=IGNORECASE | DOTALL):
        opening_tag = match.group(1)
        body = match.group("body")
        detail_url = urljoin(base_url, attr_value(opening_tag, "href"))
        if detail_url in seen or not is_allowed_globo_article_url(detail_url):
            continue

        title = attr_value(opening_tag, "title")
        if not title:
            title_match = search(r'<h2\b[^>]*class=["\'][^"\']*post__title[^"\']*["\'][^>]*>(.*?)</h2>', body, flags=IGNORECASE | DOTALL)
            title = strip_tags(title_match.group(1)) if title_match else strip_tags(body)
        if not title:
            continue

        image_url = ""
        image_match = search(r"<img\b[^>]*>", body, flags=IGNORECASE | DOTALL)
        if image_match:
            candidate = urljoin(base_url, attr_value(image_match.group(0), "src"))
            if is_allowed_globo_image_url(candidate):
                image_url = candidate

        cards.append(
            {
                "title": title,
                "detail_url": detail_url,
                "category": category_for_link(html[max(0, match.start() - 1800):match.start()], detail_url),
                "image_url": image_url,
            }
        )
        seen.add(detail_url)
        if len(cards) >= max_articles:
            break

    return cards


def meta_content(html: str, property_name: str) -> str:
    property_pattern = rf'<meta\b(?=[^>]*(?:property|name)=["\']{property_name}["\'])(?=[^>]*content=["\'](?P<content>[^"\']+)["\'])[^>]*>'
    match = search(property_pattern, html, flags=IGNORECASE | DOTALL)
    return unescape(match.group("content")).strip() if match else ""


def first_text(html: str, selector_class: str, tag: str = r"[a-z0-9]+") -> str:
    if not selector_class:
        match = search(rf"<{tag}\b[^>]*>(?P<body>.*?)</{tag}>", html, flags=IGNORECASE | DOTALL)
        return strip_tags(match.group("body")) if match else ""
    match = search(
        rf'<{tag}\b[^>]*class=["\'][^"\']*{selector_class}[^"\']*["\'][^>]*>(?P<body>.*?)</{tag}>',
        html,
        flags=IGNORECASE | DOTALL,
    )
    return strip_tags(match.group("body")) if match else ""


def clean_globo_title(title: str) -> str:
    title = " ".join(title.split())
    for separator in (" | ", " - "):
        if separator in title:
            return title.split(separator, 1)[0].strip()
    return title


def parse_globo_article_detail(html: str) -> dict[str, str]:
    title = (
        meta_content(html, "og:title")
        or first_text(html, "content-head__title", "h1")
        or first_text(html, "", "h1")
    )
    description = (
        meta_content(html, "og:description")
        or meta_content(html, "description")
        or first_text(html, "content-head__subtitle", "h2")
    )
    image_url = meta_content(html, "og:image")
    if image_url and not is_allowed_globo_image_url(image_url):
        image_url = ""

    return {
        "title": clean_globo_title(title),
        "description": " ".join(description.split()),
        "image_url": image_url,
    }


def extract_globo_external_id(detail_url: str) -> str:
    parsed = urlparse(detail_url)
    raw = f"{parsed.netloc}{parsed.path.removesuffix('.ghtml')}"
    slug = sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    if len(slug) <= 110:
        return slug
    tail = slug[-82:]
    prefix = slug[:20]
    return f"{prefix}-{tail}".strip("-")


def image_extension(image_url: str) -> str:
    suffix = Path(urlparse(image_url).path).suffix.lower().lstrip(".")
    if suffix in {"jpg", "jpeg", "png", "webp"}:
        return "jpg" if suffix == "jpeg" else suffix
    return "jpg"


def globo_image_paths(*, media_root: str, external_id: str, image_url: str) -> tuple[str, str]:
    extension = image_extension(image_url)
    filename = f"{external_id}.{extension}"
    image_path = str(Path(media_root) / "globo" / filename)
    public_path = f"/media/globo/{filename}"
    return image_path, public_path


def build_globo_record_payload(
    *,
    title: str,
    category: str,
    detail_url: str,
    description: str,
    image_original_url: str,
    image_path: str,
    image_public_path: str,
) -> dict:
    return {
        "source": "globo-home",
        "category": category,
        "title": title,
        "detail_url": detail_url,
        "description": description,
        "image_original_url": image_original_url,
        "image_path": image_path,
        "image_public_path": image_public_path,
    }
