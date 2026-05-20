from __future__ import annotations

import logging

from app.scraping.sources.betano import BETANO_HOST, scrape_betano_football
from app.scraping.sources.books import BOOKS_TO_SCRAPE_HOST, scrape_books_to_scrape
from app.scraping.runtime.browser_profile import launch_betano_browser_context, read_browser_egress_ip
from app.captcha.base import CaptchaResolverProvider
from app.scraping.runtime.debug_artifacts import mask_proxy_url
from app.proxy.free_proxy import get_free_working_proxy
from app.scraping.sources.globo import GLOBO_HOME_HOST, scrape_globo_home
from app.resilience.host_policy import host_from_url
from app.proxy.manager import ProxyProfileState
from app.scraping.contracts import LoginCredentials, ScrapedRecord
from app.scraping.sources.target_site import scrape_target_site


logger = logging.getLogger(__name__)


async def scrape_with_playwright(
    *,
    start_url: str,
    max_pages: int,
    proxy: ProxyProfileState,
    captcha_provider: CaptchaResolverProvider,
    login_credentials: LoginCredentials,
    page_timeout_seconds: int,
    gbp_to_brl_rate: float = 6.5,
    media_root: str = "/app/media",
    public_api_url: str = "http://localhost:8000",
    globo_max_articles: int = 12,
    betano_max_leagues: int = 10,
    betano_proxy_url: str = "",
    betano_debug_artifacts: bool = False,
    betano_debug_max_artifacts: int = 40,
) -> list[ScrapedRecord]:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        if host_from_url(start_url) == BETANO_HOST:
            if betano_proxy_url == "auto":
                betano_proxy_url = await get_free_working_proxy()

            betano_browser, betano_context, session_path, storage_state = await launch_betano_browser_context(
                playwright,
                betano_proxy_url=betano_proxy_url,
            )
            betano_page = await betano_context.new_page()
            betano_page.set_default_timeout(page_timeout_seconds * 1000)
            betano_egress_ip = await read_browser_egress_ip(betano_page, betano_proxy_url)
            logger.info(
                "Betano browser configurado com proxy=%s egress_ip=%s storage_state=%s",
                mask_proxy_url(betano_proxy_url),
                betano_egress_ip or "desconhecido",
                "sim" if storage_state else "nao",
            )
            try:
                return await scrape_betano_football(
                    page=betano_page,
                    context=betano_context,
                    start_url=start_url,
                    proxy=proxy,
                    max_leagues=betano_max_leagues,
                    session_path=session_path,
                    media_root=media_root,
                    public_api_url=public_api_url,
                    debug_artifacts=betano_debug_artifacts,
                    debug_max_artifacts=betano_debug_max_artifacts,
                    betano_proxy_url=betano_proxy_url,
                    betano_egress_ip=betano_egress_ip,
                )
            finally:
                await betano_browser.close()

        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            extra_http_headers={"X-Lab-Proxy-Id": proxy.name},
            user_agent="ScaleScrapeLab/1.0",
        )
        page = await context.new_page()
        page.set_default_timeout(page_timeout_seconds * 1000)

        try:
            if host_from_url(start_url) == BOOKS_TO_SCRAPE_HOST:
                return await scrape_books_to_scrape(
                    page=page,
                    start_url=start_url,
                    max_pages=max_pages,
                    proxy=proxy,
                    gbp_to_brl_rate=gbp_to_brl_rate,
                    page_timeout_seconds=page_timeout_seconds,
                )

            if host_from_url(start_url) == GLOBO_HOME_HOST:
                return await scrape_globo_home(
                    page=page,
                    start_url=start_url,
                    max_pages=max_pages,
                    proxy=proxy,
                    page_timeout_seconds=page_timeout_seconds,
                    media_root=media_root,
                    max_articles=globo_max_articles,
                )

            return await scrape_target_site(
                page=page,
                start_url=start_url,
                max_pages=max_pages,
                proxy=proxy,
                captcha_provider=captcha_provider,
                login_credentials=login_credentials,
            )
        finally:
            await browser.close()
