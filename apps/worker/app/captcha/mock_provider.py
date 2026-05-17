from app.captcha.base import CaptchaResolverProvider


class MockCaptchaResolverProvider(CaptchaResolverProvider):
    def __init__(self, answer: str = "ABCDE") -> None:
        self.answer = answer

    def solve_image_captcha(self, image_bytes: bytes, source_host: str) -> str:
        return self.answer

