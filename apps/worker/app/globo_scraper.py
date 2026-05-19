from __future__ import annotations

from pathlib import Path

from app.globo import (
    build_globo_record_payload,
    extract_globo_external_id,
    globo_image_paths,
    is_allowed_globo_image_url,
    parse_globo_article_detail,
    parse_globo_home_cards,
)
from app.proxy.manager import ProxyProfileState
from app.scraper_contracts import ScrapedRecord, ScrapeBlocked


GLOBO_HOME_HOST = "www.globo.com"


async def scrape_globo_home(
    *,
    page,
    start_url: str,
    max_pages: int,
    proxy: ProxyProfileState,
    page_timeout_seconds: int,
    media_root: str,
    max_articles: int,
) -> list[ScrapedRecord]:
    response = await page.goto(start_url, wait_until="domcontentloaded")
    status = response.status if response else 0
    if status in (403, 429):
        raise ScrapeBlocked(status, f"bloqueio HTTP {status}")

    html = await page.content()
    cards = parse_globo_home_cards(html, base_url=start_url, max_articles=max_articles * max_pages)
    if not cards:
        raise RuntimeError("layout globo sem links .post__link")

    detail_page = await page.context.new_page()
    detail_page.set_default_timeout(page_timeout_seconds * 1000)
    records: list[ScrapedRecord] = []
    try:
        for card in cards[:max_articles]:
            detail_url = card["detail_url"]
            detail = {"title": card["title"], "description": "", "image_url": card["image_url"]}
            detail_response = await detail_page.goto(detail_url, wait_until="domcontentloaded")
            detail_status = detail_response.status if detail_response else 0
            if detail_status in (403, 429):
                raise ScrapeBlocked(detail_status, f"bloqueio HTTP {detail_status} no detalhe Globo")
            if 200 <= detail_status < 400:
                detail = {**detail, **parse_globo_article_detail(await detail_page.content())}

            title = detail["title"] or card["title"]
            image_original_url = detail["image_url"] or card["image_url"]
            external_id = extract_globo_external_id(detail_url)
            image_path = ""
            image_public_path = ""
            if is_allowed_globo_image_url(image_original_url):
                image_path, image_public_path = await download_globo_image(
                    page=detail_page,
                    image_url=image_original_url,
                    external_id=external_id,
                    media_root=media_root,
                )

            payload = build_globo_record_payload(
                title=title,
                category=card["category"],
                detail_url=detail_url,
                description=detail["description"],
                image_original_url=image_original_url,
                image_path=image_path,
                image_public_path=image_public_path,
            )
            records.append(
                ScrapedRecord(
                    external_id=external_id,
                    title=title,
                    detail_url=detail_url,
                    raw_data={**payload, "proxy": proxy.name},
                )
            )
    finally:
        await detail_page.close()

    return records


async def download_globo_image(*, page, image_url: str, external_id: str, media_root: str) -> tuple[str, str]:
    if not is_allowed_globo_image_url(image_url):
        return "", ""

    response = await page.context.request.get(
        image_url,
        headers={"user-agent": "ScaleScrapeLab/1.0"},
        timeout=15000,
    )
    if not response.ok:
        return "", ""

    image_path, image_public_path = globo_image_paths(
        media_root=media_root,
        external_id=external_id,
        image_url=image_url,
    )
    target = Path(image_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(await response.body())
    return image_path, image_public_path
