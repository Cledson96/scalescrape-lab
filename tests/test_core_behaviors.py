import asyncio
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NoopMetric:
    def labels(self, **kwargs):  # noqa: ANN001
        return self

    def inc(self, amount: int = 1) -> None:
        return None

    def set(self, value: int) -> None:
        return None

    def observe(self, value: float) -> None:
        return None


sys.modules.setdefault(
    "prometheus_client",
    types.SimpleNamespace(
        Counter=lambda *args, **kwargs: NoopMetric(),
        Gauge=lambda *args, **kwargs: NoopMetric(),
        Histogram=lambda *args, **kwargs: NoopMetric(),
    ),
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


worker_policy = load_module("worker_policy", ROOT / "apps" / "worker" / "app" / "policy.py")
worker_proxy = load_module("worker_proxy", ROOT / "apps" / "worker" / "app" / "proxy" / "manager.py")
api_dto = load_module("api_dto", ROOT / "apps" / "api" / "app" / "schemas" / "dto.py")
sys.path.insert(0, str(ROOT / "apps" / "worker"))
from app.policy import PolicyError as AppPolicyError  # noqa: E402
from app.captcha.two_captcha_provider import (  # noqa: E402
    TwoCaptchaConfig,
    TwoCaptchaImageResolverProvider,
)
from app.books import (  # noqa: E402
    build_books_record_payload,
    extract_book_external_id,
    parse_books_price,
    parse_rating_class,
)
from app.globo import (  # noqa: E402
    build_globo_record_payload,
    extract_globo_external_id,
    is_allowed_globo_image_url,
    parse_globo_article_detail,
    parse_globo_home_cards,
)
from app.schedule import scheduled_scrape_jobs  # noqa: E402
from app.scraper import (  # noqa: E402
    LoginCredentials,
    betano_block_message,
    betano_no_league_tabs_message,
    handle_login_if_present,
    mask_proxy_url,
)

PolicyError = worker_policy.PolicyError
ensure_host_allowed = worker_policy.ensure_host_allowed
ProxyManager = worker_proxy.ProxyManager
ProxyProfileState = worker_proxy.ProxyProfileState
ScrapedItemRead = api_dto.ScrapedItemRead


class PolicyTests(unittest.TestCase):
    def test_blocks_external_host_for_captcha_solver(self) -> None:
        with self.assertRaises(PolicyError):
            ensure_host_allowed("https://example.com/page", {"localhost"}, "captcha_solver")

    def test_allows_local_target_host(self) -> None:
        host = ensure_host_allowed(
            "http://target-site:4000/protected/items",
            {"target-site", "localhost"},
            "captcha_solver",
        )
        self.assertEqual(host, "target-site")


class ProxyManagerTests(unittest.TestCase):
    def test_selects_least_loaded_active_proxy(self) -> None:
        manager = ProxyManager(
            [
                ProxyProfileState("proxy-a", current_active_jobs=2),
                ProxyProfileState("proxy-b", current_active_jobs=0),
            ]
        )
        selected = manager.select()
        self.assertEqual(selected.name, "proxy-b")
        self.assertEqual(selected.current_active_jobs, 1)

    def test_moves_proxy_to_cooldown_after_repeated_rate_limits(self) -> None:
        proxy = ProxyProfileState("proxy-a")
        manager = ProxyManager([proxy], cooldown_seconds=60)
        proxy.current_active_jobs = 1
        manager.release("proxy-a", "rate_limited")
        proxy.current_active_jobs = 1
        manager.release("proxy-a", "rate_limited")
        proxy.current_active_jobs = 1
        manager.release("proxy-a", "rate_limited")
        self.assertEqual(proxy.status, "cooldown")
        self.assertIsNotNone(proxy.cooldown_until)


class WorkerCaptchaPolicyTests(unittest.TestCase):
    def test_two_captcha_provider_refuses_disabled_real_solver(self) -> None:
        provider = TwoCaptchaImageResolverProvider(
            TwoCaptchaConfig(
                api_key="fake",
                allowed_hosts={"target-site"},
                enabled=False,
                max_solves_per_run=1,
            )
        )
        with self.assertRaises(RuntimeError):
            provider.solve_image_captcha(b"image", "target-site")

    def test_two_captcha_provider_blocks_external_host_before_calling_network(self) -> None:
        provider = TwoCaptchaImageResolverProvider(
            TwoCaptchaConfig(
                api_key="fake",
                allowed_hosts={"target-site"},
                enabled=True,
                max_solves_per_run=1,
            )
        )
        with self.assertRaises(AppPolicyError):
            provider.solve_image_captcha(b"image", "example.com")


class FakeLocator:
    def __init__(self, count: int = 1, attr: str | None = None, screenshot: bytes = b"image") -> None:
        self._count = count
        self._attr = attr
        self._screenshot = screenshot
        self.filled_value: str | None = None
        self.clicked = False

    @property
    def first(self) -> "FakeLocator":
        return self

    async def count(self) -> int:
        return self._count

    async def get_attribute(self, name: str) -> str | None:
        if name in ("data-challenge-id", "data-sitekey"):
            return self._attr
        return None

    async def screenshot(self, type: str) -> bytes:  # noqa: A002
        return self._screenshot

    async def fill(self, value: str) -> None:
        self.filled_value = value

    async def click(self) -> None:
        self.clicked = True


class FakeLoginPage:
    def __init__(self) -> None:
        self.locators = {
            "#login-form": FakeLocator(),
            ".g-recaptcha": FakeLocator(count=0),
            "#captcha-challenge": FakeLocator(attr="challenge-1"),
            "#captcha-image": FakeLocator(screenshot=b"captcha-bytes"),
            "input[name='username']": FakeLocator(),
            "input[name='password']": FakeLocator(),
            "input[name='captcha_answer']": FakeLocator(),
            "#login-form button[type='submit']": FakeLocator(),
        }
        self.url = "http://target-site:4000/login"
        self.waited_for: list[str] = []
        self.expected_navigation: str | None = None
        self.evaluated: list[tuple[str, str]] = []

    def locator(self, selector: str) -> FakeLocator:
        return self.locators.get(selector, FakeLocator(count=0))

    async def evaluate(self, script: str, arg: str) -> None:
        self.evaluated.append((script, arg))

    def expect_navigation(self, wait_until: str):
        page = self

        class ExpectedNavigation:
            async def __aenter__(self):
                page.expected_navigation = wait_until

            async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
                return False

        return ExpectedNavigation()

    async def wait_for_load_state(self, state: str) -> None:
        self.waited_for.append(state)


class RecordingCaptchaProvider:
    def __init__(self, answer: str = "ABCDE") -> None:
        self.answer = answer
        self.calls: list[tuple[bytes, str]] = []
        self.recaptcha_calls: list[tuple[str, str, str]] = []

    def solve_image_captcha(self, image_bytes: bytes, source_host: str) -> str:
        self.calls.append((image_bytes, source_host))
        return self.answer

    def solve_recaptcha(self, sitekey: str, page_url: str, source_host: str) -> str:
        self.recaptcha_calls.append((sitekey, page_url, source_host))
        return self.answer


class WorkerLoginFlowTests(unittest.TestCase):
    def test_login_handler_solves_local_captcha_and_submits_credentials(self) -> None:
        page = FakeLoginPage()
        provider = RecordingCaptchaProvider(answer="SOLVED")

        handled = asyncio.run(
            handle_login_if_present(
                page,
                "http://target-site:4000/protected/items?page=1",
                provider,
                LoginCredentials(username="demo", password="demo123"),
            )
        )

        self.assertTrue(handled)
        self.assertEqual(provider.calls, [(b"captcha-bytes", "target-site")])
        self.assertEqual(provider.recaptcha_calls, [])
        self.assertEqual(page.locators["input[name='username']"].filled_value, "demo")
        self.assertEqual(page.locators["input[name='password']"].filled_value, "demo123")
        self.assertEqual(page.locators["input[name='captcha_answer']"].filled_value, "SOLVED")
        self.assertTrue(page.locators["#login-form button[type='submit']"].clicked)
        self.assertEqual(page.expected_navigation, "domcontentloaded")
        self.assertEqual(page.waited_for, [])

    def test_login_handler_solves_recaptcha_and_submits_credentials(self) -> None:
        page = FakeLoginPage()
        page.locators[".g-recaptcha"] = FakeLocator(count=1, attr="test-site-key")
        provider = RecordingCaptchaProvider(answer="TOKEN123")

        handled = asyncio.run(
            handle_login_if_present(
                page,
                "http://target-site:4000/protected/items?page=1",
                provider,
                LoginCredentials(username="demo", password="demo123"),
            )
        )

        self.assertTrue(handled)
        self.assertEqual(provider.calls, [])
        self.assertEqual(provider.recaptcha_calls, [("test-site-key", "http://scalescrape.cledson.com.br:4000/login", "target-site")])
        self.assertEqual(page.locators["input[name='username']"].filled_value, "demo")
        self.assertEqual(page.locators["input[name='password']"].filled_value, "demo123")
        self.assertTrue(page.locators["#login-form button[type='submit']"].clicked)
        self.assertEqual(len(page.evaluated), 1)
        self.assertEqual(page.evaluated[0][1], "TOKEN123")


class BooksToScrapeParserTests(unittest.TestCase):
    def test_parse_books_price_converts_gbp_to_brl_with_configured_rate(self) -> None:
        price = parse_books_price("£37.59", gbp_to_brl_rate=6.5)

        self.assertEqual(price["currency"], "GBP")
        self.assertEqual(price["amount"], 37.59)
        self.assertEqual(price["formatted"], "£37.59")
        self.assertEqual(price["brl_currency"], "BRL")
        self.assertEqual(price["brl_amount"], 244.34)
        self.assertEqual(price["brl_formatted"], "R$ 244,34")
        self.assertEqual(price["exchange_rate"], 6.5)

    def test_parse_rating_class_reads_books_to_scrape_rating_label_and_value(self) -> None:
        rating = parse_rating_class("star-rating Three")

        self.assertEqual(rating, {"label": "Three", "value": 3})

    def test_extract_book_external_id_uses_detail_slug(self) -> None:
        external_id = extract_book_external_id(
            "https://books.toscrape.com/catalogue/dune-dune-1_151/index.html"
        )

        self.assertEqual(external_id, "dune-dune-1_151")

    def test_build_books_record_payload_keeps_required_demo_fields(self) -> None:
        payload = build_books_record_payload(
            title="Dune (Dune #1)",
            category="science-fiction",
            detail_url="https://books.toscrape.com/catalogue/dune-dune-1_151/index.html",
            price_text="£54.86",
            rating_class="star-rating One",
            description="Set in the far future.",
            availability="In stock",
            gbp_to_brl_rate=6.5,
        )

        self.assertEqual(payload["source"], "books-to-scrape")
        self.assertEqual(payload["category"], "science-fiction")
        self.assertEqual(payload["title"], "Dune (Dune #1)")
        self.assertEqual(payload["price"]["amount"], 54.86)
        self.assertEqual(payload["price"]["brl_amount"], 356.59)
        self.assertEqual(payload["rating"], {"label": "One", "value": 1})
        self.assertEqual(payload["description"], "Set in the far future.")
        self.assertEqual(payload["availability"], "In stock")


class ScheduledScrapeTests(unittest.TestCase):
    def test_scheduled_scrape_jobs_runs_all_demo_sources_every_six_hours(self) -> None:
        jobs = scheduled_scrape_jobs(interval_seconds=21600)

        self.assertEqual(
            [job["source"] for job in jobs],
            ["fake-target", "books-to-scrape", "globo-home", "betano-football"],
        )
        self.assertEqual(jobs[0]["start_url"], "http://target-site:4000/protected/items?page=1")
        self.assertEqual(
            jobs[1]["start_url"],
            "https://books.toscrape.com/catalogue/category/books/science-fiction_16/index.html",
        )
        self.assertEqual(jobs[2]["start_url"], "https://www.globo.com/")
        self.assertEqual(jobs[3]["start_url"], "https://www.betano.bet.br/sport/futebol/")
        self.assertTrue(all(job["mode"] == "browser" for job in jobs))
        self.assertTrue(all(job["interval_seconds"] == 21600 for job in jobs))


class BetanoDiagnosticsTests(unittest.TestCase):
    def test_mask_proxy_url_hides_credentials(self) -> None:
        self.assertEqual(
            mask_proxy_url("socks5://user:secret@100.81.81.109:1080"),
            "socks5://***:***@100.81.81.109:1080",
        )
        self.assertEqual(mask_proxy_url("socks5://100.81.81.109:1080"), "socks5://100.81.81.109:1080")

    def test_betano_block_message_includes_proxy_and_egress_ip(self) -> None:
        self.assertEqual(
            betano_block_message(403, "socks5://100.81.81.109:1080", "186.214.56.189"),
            "bloqueio HTTP 403 no Betano (proxy=socks5://100.81.81.109:1080, egress_ip=186.214.56.189)",
        )

    def test_betano_no_league_tabs_message_includes_page_diagnostics(self) -> None:
        self.assertEqual(
            betano_no_league_tabs_message(42, 9, "https://www.betano.bet.br/sport/futebol/"),
            (
                "Nenhuma aba de liga encontrada na secao POPULARES do Betano "
                "(clickables=42, odds=9, url=https://www.betano.bet.br/sport/futebol/)"
            ),
        )


class GloboParserTests(unittest.TestCase):
    def test_parse_globo_home_cards_reads_category_title_link_and_image(self) -> None:
        html = """
        <div data-tracking-action="jornalismo">
          <a class="post__link" href="https://g1.globo.com/saude/noticia/2026/05/18/remedio.ghtml" title="Remedio recolhido">
            <figure><img class="post__image" src="https://s2-home-globo.glbimg.com/foto.jpg" /></figure>
            <h2 class="post__title">Remedio recolhido</h2>
          </a>
        </div>
        <div data-tracking-action="esporte">
          <a class="post__link" href="https://example.com/noticia.ghtml" title="Ignorar">
            <h2 class="post__title">Ignorar</h2>
          </a>
        </div>
        """

        cards = parse_globo_home_cards(html, base_url="https://www.globo.com/")

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["category"], "jornalismo")
        self.assertEqual(cards[0]["title"], "Remedio recolhido")
        self.assertEqual(cards[0]["detail_url"], "https://g1.globo.com/saude/noticia/2026/05/18/remedio.ghtml")
        self.assertEqual(cards[0]["image_url"], "https://s2-home-globo.glbimg.com/foto.jpg")

    def test_parse_globo_article_detail_prefers_open_graph_metadata(self) -> None:
        html = """
        <html>
          <head>
            <meta property="og:title" content="Titulo final | G1" />
            <meta property="og:description" content="Resumo da noticia para o dashboard." />
            <meta property="og:image" content="https://s2-g1.glbimg.com/final.jpg" />
          </head>
          <body>
            <h1 class="content-head__title">Titulo no H1</h1>
          </body>
        </html>
        """

        detail = parse_globo_article_detail(html)

        self.assertEqual(detail["title"], "Titulo final")
        self.assertEqual(detail["description"], "Resumo da noticia para o dashboard.")
        self.assertEqual(detail["image_url"], "https://s2-g1.glbimg.com/final.jpg")

    def test_build_globo_record_payload_keeps_demo_fields(self) -> None:
        payload = build_globo_record_payload(
            title="Titulo final",
            category="jornalismo",
            detail_url="https://g1.globo.com/saude/noticia/2026/05/18/remedio.ghtml",
            description="Resumo da noticia.",
            image_original_url="https://s2-g1.glbimg.com/final.jpg",
            image_path="/app/media/globo/remedio.jpg",
            image_public_path="/media/globo/remedio.jpg",
        )

        self.assertEqual(payload["source"], "globo-home")
        self.assertEqual(payload["category"], "jornalismo")
        self.assertEqual(payload["title"], "Titulo final")
        self.assertEqual(payload["description"], "Resumo da noticia.")
        self.assertEqual(payload["image_original_url"], "https://s2-g1.glbimg.com/final.jpg")
        self.assertEqual(payload["image_path"], "/app/media/globo/remedio.jpg")
        self.assertEqual(payload["image_public_path"], "/media/globo/remedio.jpg")

    def test_globo_helpers_limit_hosts_and_stable_external_id(self) -> None:
        external_id = extract_globo_external_id(
            "https://g1.globo.com/saude/noticia/2026/05/18/remedio.ghtml"
        )

        self.assertEqual(external_id, "g1-globo-com-saude-noticia-2026-05-18-remedio")
        self.assertTrue(is_allowed_globo_image_url("https://s2-g1.glbimg.com/final.jpg"))
        self.assertFalse(is_allowed_globo_image_url("https://example.com/final.jpg"))


class ApiItemsSchemaTests(unittest.TestCase):
    def test_job_read_exposes_public_url_for_internal_target_site_url(self) -> None:
        previous = os.environ.get("PUBLIC_TARGET_SITE_URL")
        os.environ["PUBLIC_TARGET_SITE_URL"] = "https://dev.scalescrape.cledson.com.br"
        try:
            job = api_dto.JobRead.model_validate(
                {
                    "id": 12,
                    "source_id": 1,
                    "start_url": "http://target-site:4000/protected/items?page=1",
                    "status": "success",
                    "mode": "browser",
                    "max_pages": 1,
                    "attempts": 0,
                    "items_found": 12,
                    "error_message": None,
                    "created_at": "2026-05-18T21:52:13.392016",
                }
            )
            self.assertEqual(
                job.public_url,
                "https://dev.scalescrape.cledson.com.br/protected/items?page=1",
            )
        finally:
            if previous is None:
                os.environ.pop("PUBLIC_TARGET_SITE_URL", None)
            else:
                os.environ["PUBLIC_TARGET_SITE_URL"] = previous

    def test_scraped_item_read_exposes_raw_extracted_data(self) -> None:
        previous = os.environ.get("PUBLIC_TARGET_SITE_URL")
        previous_public_api = os.environ.get("PUBLIC_API_URL")
        os.environ["PUBLIC_TARGET_SITE_URL"] = "https://dev.scalescrape.cledson.com.br"
        os.environ["PUBLIC_API_URL"] = "https://api-dev.scalescrape.cledson.com.br"
        item = ScrapedItemRead.model_validate(
            {
                "id": 10,
                "job_id": 2,
                "external_id": "dune-dune-1_151",
                "title": "Dune (Dune #1)",
                "detail_url": "http://target-site:4000/items/protected-1",
                "raw_data": {
                    "price": {"amount": 54.86, "brl_amount": 356.59},
                    "description": "Set in the far future.",
                    "image_public_path": "/media/globo/remedio.jpg",
                },
                "created_at": "2026-05-18T12:00:00",
                "extracted_at": "2026-05-18T12:00:00",
            }
        )
        try:
            self.assertEqual(item.title, "Dune (Dune #1)")
            self.assertEqual(item.extracted_at.isoformat(), "2026-05-18T12:00:00")
            self.assertEqual(item.public_detail_url, "https://dev.scalescrape.cledson.com.br/items/protected-1")
            self.assertEqual(item.public_image_url, "https://api-dev.scalescrape.cledson.com.br/media/globo/remedio.jpg")
            self.assertEqual(item.raw_data["price"]["brl_amount"], 356.59)
            self.assertEqual(item.raw_data["description"], "Set in the far future.")
        finally:
            if previous is None:
                os.environ.pop("PUBLIC_TARGET_SITE_URL", None)
            else:
                os.environ["PUBLIC_TARGET_SITE_URL"] = previous
            if previous_public_api is None:
                os.environ.pop("PUBLIC_API_URL", None)
            else:
                os.environ["PUBLIC_API_URL"] = previous_public_api

    def test_scraped_item_page_read_exposes_pagination_metadata(self) -> None:
        item = ScrapedItemRead.model_validate(
            {
                "id": 1,
                "job_id": 1,
                "external_id": "item-1",
                "title": "Item 1",
                "detail_url": "https://www.globo.com/noticia.ghtml",
                "raw_data": {"source": "globo-home"},
                "created_at": "2026-05-18T12:00:00",
                "extracted_at": "2026-05-18T12:00:00",
            }
        )

        page = api_dto.ScrapedItemPageRead(
            items=[item],
            total=21,
            page=2,
            page_size=10,
        )

        self.assertEqual(page.total_pages, 3)
        self.assertEqual(page.items[0].raw_data["source"], "globo-home")

    def test_scraped_item_read_can_alias_created_at_as_extracted_at(self) -> None:
        class FakeScrapedItem:
            id = 11
            job_id = 3
            external_id = "join_902"
            title = "Join"
            detail_url = "https://books.toscrape.com/catalogue/join_902/index.html"
            raw_data = {"source": "books-to-scrape"}
            created_at = datetime(2026, 5, 18, 13, 30, 0)

            @property
            def extracted_at(self):
                return self.created_at

        item = ScrapedItemRead.model_validate(FakeScrapedItem())

        self.assertEqual(item.created_at.isoformat(), "2026-05-18T13:30:00")
        self.assertEqual(item.extracted_at.isoformat(), "2026-05-18T13:30:00")


if __name__ == "__main__":
    unittest.main()
