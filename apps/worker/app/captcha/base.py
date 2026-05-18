from abc import ABC, abstractmethod


class CaptchaResolverProvider(ABC):
    @abstractmethod
    def solve_image_captcha(self, image_bytes: bytes, source_host: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def solve_recaptcha(self, sitekey: str, page_url: str, source_host: str) -> str:
        """Resolve a Google reCAPTCHA v2 and return the g-recaptcha-response token."""
        raise NotImplementedError

