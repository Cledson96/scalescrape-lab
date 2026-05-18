import asyncio
import importlib.util
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
from app.scraper import LoginCredentials, handle_login_if_present  # noqa: E402

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


class ApiItemsSchemaTests(unittest.TestCase):
    def test_scraped_item_read_exposes_raw_extracted_data(self) -> None:
        item = ScrapedItemRead.model_validate(
            {
                "id": 10,
                "job_id": 2,
                "external_id": "dune-dune-1_151",
                "title": "Dune (Dune #1)",
                "detail_url": "https://books.toscrape.com/catalogue/dune-dune-1_151/index.html",
                "raw_data": {
                    "price": {"amount": 54.86, "brl_amount": 356.59},
                    "description": "Set in the far future.",
                },
                "created_at": "2026-05-18T12:00:00",
            }
        )

        self.assertEqual(item.title, "Dune (Dune #1)")
        self.assertEqual(item.raw_data["price"]["brl_amount"], 356.59)
        self.assertEqual(item.raw_data["description"], "Set in the far future.")


if __name__ == "__main__":
    unittest.main()
