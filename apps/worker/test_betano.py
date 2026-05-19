"""Script de teste standalone para debugar o scraper Betano no Docker.

Execução: docker compose run --rm worker python test_betano.py
"""
import asyncio


async def main():
    from playwright.async_api import async_playwright

    url = "https://www.betano.bet.br/sport/futebol/"

    print("=" * 60)
    print("TESTE BETANO - DEBUG DE BLOQUEIO 403")
    print("=" * 60)

    async with async_playwright() as pw:
        # ---- Tentativa 1: Chromium headless SEM stealth ----
        print("\n[1/3] Testando Chromium headless SEM stealth...")
        browser1 = await pw.chromium.launch(headless=True)
        page1 = await browser1.new_page()
        try:
            resp = await page1.goto(url, wait_until="domcontentloaded", timeout=15000)
            status = resp.status if resp else "sem resposta"
            title = await page1.title()
            print(f"  Status: {status}")
            print(f"  Title:  {title}")
            body = await page1.evaluate("document.body?.innerText?.substring(0, 300)")
            print(f"  Body:   {body[:200] if body else '(vazio)'}")
        except Exception as e:
            print(f"  ERRO: {e}")
        await browser1.close()

        # ---- Tentativa 2: Chromium headless COM stealth completo ----
        print("\n[2/3] Testando Chromium headless COM stealth + UA real...")
        browser2 = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
            ],
        )
        context2 = await browser2.new_context(
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
            },
        )
        await context2.add_init_script("""
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
        page2 = await context2.new_page()
        try:
            resp = await page2.goto(url, wait_until="domcontentloaded", timeout=15000)
            status = resp.status if resp else "sem resposta"
            title = await page2.title()
            print(f"  Status: {status}")
            print(f"  Title:  {title}")
            body = await page2.evaluate("document.body?.innerText?.substring(0, 300)")
            print(f"  Body:   {body[:200] if body else '(vazio)'}")

            if status == 403:
                print("\n  >> 403 detectado. Esperando 6s e recarregando...")
                await page2.wait_for_timeout(6000)
                resp2 = await page2.reload(wait_until="domcontentloaded", timeout=15000)
                status2 = resp2.status if resp2 else "sem resposta"
                title2 = await page2.title()
                print(f"  Status apos reload: {status2}")
                print(f"  Title apos reload:  {title2}")
                body2 = await page2.evaluate("document.body?.innerText?.substring(0, 300)")
                print(f"  Body apos reload:   {body2[:200] if body2 else '(vazio)'}")

            # Verificar fingerprints
            fp = await page2.evaluate("""() => JSON.stringify({
                webdriver: navigator.webdriver,
                chrome: !!window.chrome,
                plugins: navigator.plugins.length,
                languages: navigator.languages,
                platform: navigator.platform,
                hardwareConcurrency: navigator.hardwareConcurrency,
                userAgent: navigator.userAgent,
            })""")
            print(f"\n  Fingerprints: {fp}")
        except Exception as e:
            print(f"  ERRO: {e}")
        await browser2.close()

        # ---- Tentativa 3: Chromium headless=False (headed, precisa DISPLAY) ----
        print("\n[3/3] Testando Chromium headless='new' (new headless mode)...")
        try:
            browser3 = await pw.chromium.launch(
                headless=True,
                args=[
                    "--headless=new",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context3 = await browser3.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )
            await context3.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            """)
            page3 = await context3.new_page()
            resp = await page3.goto(url, wait_until="domcontentloaded", timeout=15000)
            status = resp.status if resp else "sem resposta"
            title = await page3.title()
            print(f"  Status: {status}")
            print(f"  Title:  {title}")
            body = await page3.evaluate("document.body?.innerText?.substring(0, 300)")
            print(f"  Body:   {body[:200] if body else '(vazio)'}")
            await browser3.close()
        except Exception as e:
            print(f"  ERRO (esperado se sem DISPLAY): {e}")

    print("\n" + "=" * 60)
    print("TESTE CONCLUIDO")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
