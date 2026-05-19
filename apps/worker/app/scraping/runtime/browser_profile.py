from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


async def read_browser_egress_ip(page, proxy_url: str | None) -> str | None:  # noqa: ANN001
    if not proxy_url:
        return None
    try:
        response = await page.goto("https://api.ipify.org?format=text", wait_until="domcontentloaded", timeout=15000)
        status = response.status if response else 0
        if status >= 400:
            logger.warning("Falha ao consultar IP de saida pelo proxy Betano: HTTP %s", status)
            return None
        body = (await page.locator("body").inner_text(timeout=5000)).strip()
        return body[:80] if body else None
    except Exception as exc:  # pragma: no cover - diagnostico defensivo de rede
        logger.warning("Falha ao consultar IP de saida pelo proxy Betano: %s", exc)
        return None


async def launch_betano_browser_context(playwright, *, betano_proxy_url: str | None):
    session_path = ""
    storage_state = None
    betano_browser = await playwright.chromium.launch(
        headless=True,
        proxy={"server": betano_proxy_url} if betano_proxy_url else None,
        args=[
            "--headless=new",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--window-size=1280,800",
        ],
    )
    betano_context = await betano_browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        extra_http_headers={
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        },
        storage_state=storage_state,
    )
    # Align browser-exposed fields with a regular Chromium session.
    await betano_context.add_init_script("""
        // Avoid exposing automation-only webdriver state.
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

        // Provide Chrome runtime fields expected by client-side scripts.
        window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};

        // Populate plugin metadata commonly present in desktop Chromium.
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                {name: 'Native Client', filename: 'internal-nacl-plugin'},
            ],
        });

        // Keep locale signals consistent with the request headers.
        Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});

        // Match notification permission semantics from full Chromium.
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({state: Notification.permission})
                : originalQuery(parameters);

        // Keep iframe runtime fields consistent with the top-level window.
        const origGetter = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow').get;
        Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
            get: function() {
                const result = origGetter.call(this);
                if (!result) return result;
                try { result.chrome = window.chrome; } catch(e) {}
                return result;
            }
        });

        // Use stable WebGL vendor strings for reproducible sessions.
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter.call(this, parameter);
        };

        // Normalize network information exposed to page scripts.
        Object.defineProperty(navigator, 'connection', {
            get: () => ({effectiveType: '4g', rtt: 50, downlink: 10, saveData: false}),
        });

        // Expose a realistic desktop CPU profile.
        Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});

        // Keep platform aligned with the selected user agent.
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
    """)
    return betano_browser, betano_context, session_path, storage_state
