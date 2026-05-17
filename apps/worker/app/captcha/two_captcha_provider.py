from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.captcha.base import CaptchaResolverProvider
from app.policy import ensure_host_allowed


@dataclass
class TwoCaptchaConfig:
    api_key: str
    allowed_hosts: set[str]
    enabled: bool = False
    max_solves_per_run: int = 20
    poll_interval_seconds: int = 5
    timeout_seconds: int = 120


class TwoCaptchaImageResolverProvider(CaptchaResolverProvider):
    def __init__(self, config: TwoCaptchaConfig) -> None:
        self.config = config
        self.solve_count = 0

    def solve_image_captcha(self, image_bytes: bytes, source_host: str) -> str:
        ensure_host_allowed(source_host, self.config.allowed_hosts, "captcha_solver")
        if not self.config.enabled:
            raise RuntimeError("2Captcha real desativado por ENABLE_REAL_2CAPTCHA=false")
        if not self.config.api_key:
            raise RuntimeError("TWO_CAPTCHA_API_KEY nao configurada")
        if self.solve_count >= self.config.max_solves_per_run:
            raise RuntimeError("limite MAX_CAPTCHA_SOLVES_PER_RUN atingido")

        self.solve_count += 1
        captcha_id = self._submit(image_bytes)
        return self._poll(captcha_id)

    def _submit(self, image_bytes: bytes) -> str:
        body = urlencode(
            {
                "key": self.config.api_key,
                "method": "base64",
                "body": base64.b64encode(image_bytes).decode("ascii"),
                "json": 0,
            }
        ).encode("utf-8")
        request = Request("https://2captcha.com/in.php", data=body, method="POST")
        with urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
        if not payload.startswith("OK|"):
            raise RuntimeError(f"2Captcha submit falhou: {payload}")
        return payload.split("|", 1)[1]

    def _poll(self, captcha_id: str) -> str:
        deadline = time.monotonic() + self.config.timeout_seconds
        while time.monotonic() < deadline:
            time.sleep(self.config.poll_interval_seconds)
            params = urlencode(
                {
                    "key": self.config.api_key,
                    "action": "get",
                    "id": captcha_id,
                    "json": 0,
                }
            )
            with urlopen(f"https://2captcha.com/res.php?{params}", timeout=30) as response:
                payload = response.read().decode("utf-8")
            if payload == "CAPCHA_NOT_READY":
                continue
            if payload.startswith("OK|"):
                return payload.split("|", 1)[1]
            raise RuntimeError(f"2Captcha poll falhou: {payload}")
        raise TimeoutError("tempo limite aguardando resposta do 2Captcha")

