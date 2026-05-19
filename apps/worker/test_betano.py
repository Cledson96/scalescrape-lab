"""Script standalone para diagnosticar bloqueios da fonte Betano.

Execucao: docker compose run --rm worker python test_betano.py
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re


BETANO_HOME_URL = "https://www.betano.bet.br/"
BETANO_FOOTBALL_URL = "https://www.betano.bet.br/sport/futebol/"
BETANO_FOOTBALL_TODAY_URL = "https://www.betano.bet.br/sport/futebol/jogos-de-hoje/"
IPIFY_URL = "https://api.ipify.org?format=text"


def proxy_from_env() -> str:
    proxy_url = os.getenv("BETANO_PROXY_URL", "").strip()
    return "" if proxy_url.lower() == "auto" else proxy_url


def artifact_dir() -> Path:
    media_root = Path(os.getenv("MEDIA_ROOT", "/app/media"))
    path = media_root / "betano-debug"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_label(label: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", label).strip("-") or "betano"


async def page_excerpt(page) -> str:  # noqa: ANN001
    try:
        return (await page.locator("body").inner_text(timeout=2500)).strip()[:1200]
    except Exception:
        return ""


async def save_artifacts(page, *, label: str, metadata: dict) -> Path:  # noqa: ANN001
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = f"{timestamp}-{safe_label(label)}"
    base = artifact_dir() / stem
    screenshot_error = None
    html_error = None

    try:
        await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    except Exception as exc:
        screenshot_error = str(exc)

    try:
        base.with_suffix(".html").write_text(await page.content(), encoding="utf-8")
    except Exception as exc:
        html_error = str(exc)

    payload = {
        **metadata,
        "page_url": getattr(page, "url", ""),
        "title": await page.title() if not page.is_closed() else "",
        "body_excerpt": await page_excerpt(page) if not page.is_closed() else "",
        "screenshot_path": str(base.with_suffix(".png")).replace("\\", "/") if screenshot_error is None else None,
        "html_path": str(base.with_suffix(".html")).replace("\\", "/") if html_error is None else None,
        "screenshot_error": screenshot_error,
        "html_error": html_error,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = base.with_suffix(".json")
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata_path


async def read_egress_ip(page) -> str:  # noqa: ANN001
    try:
        response = await page.goto(IPIFY_URL, wait_until="domcontentloaded", timeout=15000)
        status = response.status if response else 0
        body = (await page.locator("body").inner_text(timeout=5000)).strip()
        return body[:80] if status < 400 and body else f"HTTP {status}"
    except Exception as exc:
        return f"erro: {exc}"


async def probe_url(page, *, label: str, url: str, attempt_name: str, proxy_url: str, egress_ip: str) -> int:  # noqa: ANN001
    print(f"  - {label}: {url}")
    status = 0
    error = None
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        status = response.status if response else 0
        await page.wait_for_timeout(2500)
    except Exception as exc:
        error = str(exc)

    title = ""
    body = ""
    try:
        title = await page.title()
        body = await page_excerpt(page)
    except Exception:
        pass

    metadata_path = await save_artifacts(
        page,
        label=f"{attempt_name}-{label}-{status or 'error'}",
        metadata={
            "attempt": attempt_name,
            "label": label,
            "target_url": url,
            "status_code": status,
            "error": error,
            "proxy": proxy_url or "sem proxy",
            "egress_ip": egress_ip,
        },
    )

    print(f"    status={status or 'sem resposta'} title={title!r}")
    if error:
        print(f"    erro={error}")
    print(f"    body={body[:180]!r}")
    print(f"    debug={metadata_path}")
    return status


async def accept_age_verification(page) -> bool:  # noqa: ANN001
    selectors = [
        '#age-verification-modal [data-qa="age-verification-modal-ok-button"]',
        '#age-verification-modal button:has-text("Sim")',
    ]
    for selector in selectors:
        button = page.locator(selector).first
        try:
            if await button.count() == 0:
                continue
            await button.click(timeout=5000)
            try:
                await page.locator("#age-verification-modal").wait_for(state="hidden", timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)
            return True
        except Exception:
            continue
    return False


async def close_landing_modal(page) -> bool:  # noqa: ANN001
    selectors = [
        '[data-testid="landing-modal-close-button"]',
        '[data-testid="landing-modal"] button[aria-label="Close modal"]',
    ]
    for selector in selectors:
        button = page.locator(selector).first
        try:
            if await button.count() == 0:
                continue
            await button.click(timeout=5000)
            try:
                await page.locator('[data-testid="landing-modal"]').wait_for(state="hidden", timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(500)
            return True
        except Exception:
            continue
    return False


async def click_football_from_homepage(page, *, attempt_name: str, proxy_url: str, egress_ip: str) -> None:  # noqa: ANN001
    print("  - football-click: clicando em Futebol a partir da homepage")
    error = None
    clicked_selector = ""
    clicked_href = ""
    selectors = [
        'a[href*="/sport/futebol"]',
        'a:has-text("Futebol")',
        '[role="link"]:has-text("Futebol")',
        'text="Futebol"',
    ]
    try:
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            clicked_selector = selector
            clicked_href = await locator.get_attribute("href") or ""
            await locator.scroll_into_view_if_needed(timeout=5000)
            await page.wait_for_timeout(500)
            await locator.click(timeout=10000)
            break
        if not clicked_selector:
            error = "link Futebol nao encontrado"
        else:
            try:
                await page.wait_for_url("**/sport/futebol**", timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(5000)
    except Exception as exc:
        error = str(exc)

    title = ""
    body = ""
    try:
        title = await page.title()
        body = await page_excerpt(page)
    except Exception:
        pass

    metadata_path = await save_artifacts(
        page,
        label=f"{attempt_name}-football-click",
        metadata={
            "attempt": attempt_name,
            "label": "football-click",
            "target_url": BETANO_FOOTBALL_URL,
            "clicked_selector": clicked_selector,
            "clicked_href": clicked_href,
            "error": error,
            "proxy": proxy_url or "sem proxy",
            "egress_ip": egress_ip,
        },
    )

    print(f"    selector={clicked_selector or '(nenhum)'} href={clicked_href or '(vazio)'} url={page.url}")
    print(f"    title={title!r}")
    if error:
        print(f"    erro={error}")
    print(f"    body={body[:180]!r}")
    print(f"    debug={metadata_path}")


async def run_attempt(playwright, *, name: str, proxy_url: str, args: list[str], stealth: bool) -> None:  # noqa: ANN001
    print(f"\n[{name}] Iniciando tentativa")
    browser = await playwright.chromium.launch(
        headless=True,
        proxy={"server": proxy_url} if proxy_url else None,
        args=args,
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"},
    )
    if stealth:
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                    {name: 'Native Client', filename: 'internal-nacl-plugin'},
                ],
            });
            Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
        """)

    page = await context.new_page()
    try:
        egress_ip = await read_egress_ip(page)
        print(f"  proxy={proxy_url or 'sem proxy'}")
        print(f"  egress_ip={egress_ip}")

        homepage_status = await probe_url(
            page,
            label="homepage",
            url=BETANO_HOME_URL,
            attempt_name=name,
            proxy_url=proxy_url,
            egress_ip=egress_ip,
        )
        accepted_age = await accept_age_verification(page)
        print(f"  age_verification={'aceito' if accepted_age else 'nao encontrado'}")
        closed_landing_modal = await close_landing_modal(page)
        print(f"  landing_modal={'fechado' if closed_landing_modal else 'nao encontrado'}")
        await click_football_from_homepage(page, attempt_name=name, proxy_url=proxy_url, egress_ip=egress_ip)
        football_status = await probe_url(
            page,
            label="football",
            url=BETANO_FOOTBALL_URL,
            attempt_name=name,
            proxy_url=proxy_url,
            egress_ip=egress_ip,
        )
        football_today_status = await probe_url(
            page,
            label="football-today",
            url=BETANO_FOOTBALL_TODAY_URL,
            attempt_name=name,
            proxy_url=proxy_url,
            egress_ip=egress_ip,
        )

        fp = await page.evaluate("""() => JSON.stringify({
            webdriver: navigator.webdriver,
            chrome: !!window.chrome,
            plugins: navigator.plugins.length,
            languages: navigator.languages,
            platform: navigator.platform,
            hardwareConcurrency: navigator.hardwareConcurrency,
            userAgent: navigator.userAgent,
        })""")
        print(f"  fingerprints={fp}")
        if homepage_status in (403, 429) or football_status in (403, 429) or football_today_status in (403, 429):
            print("  diagnostico=Betano bloqueou a navegacao HTTP nesta tentativa")
    finally:
        await browser.close()


async def main() -> None:
    from playwright.async_api import async_playwright

    proxy_url = proxy_from_env()
    print("=" * 72)
    print("TESTE BETANO - DIAGNOSTICO DE BLOQUEIO")
    print("=" * 72)
    print(f"BETANO_PROXY_URL={proxy_url or 'sem proxy'}")
    print(f"MEDIA_ROOT={os.getenv('MEDIA_ROOT', '/app/media')}")

    attempts = [
        {
            "name": "chromium-sem-stealth",
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
            "stealth": False,
        },
        {
            "name": "chromium-stealth",
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1280,800",
            ],
            "stealth": True,
        },
        {
            "name": "chromium-headless-new",
            "args": [
                "--headless=new",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1280,800",
            ],
            "stealth": True,
        },
    ]

    async with async_playwright() as playwright:
        for attempt in attempts:
            try:
                await run_attempt(playwright, proxy_url=proxy_url, **attempt)
            except Exception as exc:
                print(f"\n[{attempt['name']}] ERRO GERAL: {exc}")

    print("\n" + "=" * 72)
    print("TESTE CONCLUIDO")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
