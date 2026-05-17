from datetime import datetime
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


target_antibot = load_module("target_antibot", ROOT / "apps" / "target_site" / "app" / "antibot.py")
target_captcha = load_module("target_captcha", ROOT / "apps" / "target_site" / "app" / "captcha.py")
worker_policy = load_module("worker_policy", ROOT / "apps" / "worker" / "app" / "policy.py")
worker_proxy = load_module("worker_proxy", ROOT / "apps" / "worker" / "app" / "proxy" / "manager.py")
sys.path.insert(0, str(ROOT / "apps" / "worker"))
from app.policy import PolicyError as AppPolicyError  # noqa: E402
from app.captcha.two_captcha_provider import (  # noqa: E402
    TwoCaptchaConfig,
    TwoCaptchaImageResolverProvider,
)

AntibotAction = target_antibot.AntibotAction
AntibotSimulator = target_antibot.AntibotSimulator
CaptchaStore = target_captcha.CaptchaStore
PolicyError = worker_policy.PolicyError
ensure_host_allowed = worker_policy.ensure_host_allowed
ProxyManager = worker_proxy.ProxyManager
ProxyProfileState = worker_proxy.ProxyProfileState


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


class AntibotTests(unittest.TestCase):
    def test_requires_challenge_for_suspicious_session_without_cookie(self) -> None:
        simulator = AntibotSimulator()
        decision = None
        for index in range(8):
            decision = simulator.evaluate(
                session_id="session-a",
                proxy_id="proxy-a",
                path="/protected/items",
                user_agent="SuspiciousBot/1.0",
                has_clearance_cookie=False,
                now=datetime(2026, 1, 1, 10, 0, index),
            )
        self.assertIsNotNone(decision)
        self.assertEqual(decision.action, AntibotAction.CHALLENGE)

    def test_rate_limits_excessive_session(self) -> None:
        simulator = AntibotSimulator()
        decision = None
        for index in range(12):
            decision = simulator.evaluate(
                session_id="session-b",
                proxy_id="proxy-a",
                path="/protected/items",
                user_agent="ScaleScrapeLab/1.0",
                has_clearance_cookie=False,
                now=datetime(2026, 1, 1, 10, 0, index),
            )
        self.assertEqual(decision.action, AntibotAction.RATE_LIMIT)


class CaptchaTests(unittest.TestCase):
    def test_captcha_store_generates_image_and_verifies_answer(self) -> None:
        store = CaptchaStore()
        challenge = store.create()
        payload = store.render_png(challenge.challenge_id)
        self.assertTrue(payload.startswith(b"\x89PNG"))
        self.assertTrue(store.verify(challenge.challenge_id, challenge.expected_answer.lower()))

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


if __name__ == "__main__":
    unittest.main()
