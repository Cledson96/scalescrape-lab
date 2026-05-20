from __future__ import annotations

import random
from pathlib import Path


async def browser_paced_click(element, page) -> None:  # noqa: ANN001
    """Execute a browser-paced click with scroll, hover and small timing variance."""
    await element.scroll_into_view_if_needed()
    await page.wait_for_timeout(random.randint(200, 500))
    await element.hover()
    await page.wait_for_timeout(random.randint(100, 350))
    await element.click()


async def accept_betano_age_verification(page) -> bool:  # noqa: ANN001
    selectors = [
        '#age-verification-modal [data-qa="age-verification-modal-ok-button"]',
        '#age-verification-modal button:has-text("Sim")',
    ]
    for selector in selectors:
        button = page.locator(selector).first
        try:
            if await button.count() == 0:
                continue
            await browser_paced_click(button, page)
            try:
                await page.locator("#age-verification-modal").wait_for(state="hidden", timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)
            return True
        except Exception:
            continue
    return False


async def close_betano_landing_modal(page) -> bool:  # noqa: ANN001
    selectors = [
        '[data-testid="landing-modal-close-button"]',
        '[data-testid="landing-modal"] button[aria-label="Close modal"]',
    ]
    for selector in selectors:
        button = page.locator(selector).first
        try:
            if await button.count() == 0:
                continue
            await browser_paced_click(button, page)
            try:
                await page.locator('[data-testid="landing-modal"]').wait_for(state="hidden", timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(500)
            return True
        except Exception:
            continue
    return False


async def reset_betano_browser_state(page, context, session_path: str = "") -> bool:  # noqa: ANN001
    removed_session = False
    try:
        await context.clear_cookies()
    except Exception:
        pass

    try:
        await page.evaluate("""() => {
            window.localStorage?.clear();
            window.sessionStorage?.clear();
        }""")
    except Exception:
        pass

    if session_path:
        try:
            path = Path(session_path)
            if path.exists():
                path.unlink()
                removed_session = True
        except Exception:
            pass
    return removed_session


async def click_betano_football_from_homepage(page) -> dict:  # noqa: ANN001
    result = {
        "clicked": False,
        "selector": "",
        "href": "",
        "mouse_response_status": 0,
        "mouse_response_url": "",
        "keyboard_response_status": 0,
        "keyboard_response_url": "",
        "url_after_click": "",
        "error": "",
    }
    selectors = [
        'a[href*="/sport/futebol"]',
        'a:has-text("Futebol")',
        '[role="link"]:has-text("Futebol")',
        'text="Futebol"',
    ]
    for selector in selectors:
        locator = page.locator(selector)
        try:
            count = await locator.count()
        except Exception:
            continue
        for index in range(min(count, 10)):
            candidate = locator.nth(index)
            try:
                if not await candidate.is_visible(timeout=1000):
                    continue
                result["selector"] = selector
                result["href"] = await candidate.get_attribute("href") or ""
                try:
                    async with page.expect_response(lambda response: "/sport/futebol" in response.url, timeout=12000) as response_info:
                        await browser_paced_click(candidate, page)
                    response = await response_info.value
                    result["mouse_response_status"] = response.status
                    result["mouse_response_url"] = response.url
                except Exception as exc:
                    result["error"] = str(exc)

                if "/sport/futebol" not in page.url:
                    try:
                        await candidate.focus()
                        async with page.expect_response(
                            lambda response: "/sport/futebol" in response.url,
                            timeout=12000,
                        ) as keyboard_response_info:
                            await page.keyboard.press("Enter")
                        keyboard_response = await keyboard_response_info.value
                        result["keyboard_response_status"] = keyboard_response.status
                        result["keyboard_response_url"] = keyboard_response.url
                    except Exception as exc:
                        if not result["error"]:
                            result["error"] = str(exc)

                await page.wait_for_timeout(1500)
                result["url_after_click"] = page.url
                result["clicked"] = bool(
                    result["mouse_response_status"]
                    or result["keyboard_response_status"]
                    or "/sport/futebol" in page.url
                )
                return result
            except Exception as exc:
                result["error"] = str(exc)
                continue
    result["url_after_click"] = page.url
    if not result["error"]:
        result["error"] = "link Futebol visivel nao encontrado"
    return result
