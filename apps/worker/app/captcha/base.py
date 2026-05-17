from abc import ABC, abstractmethod


class CaptchaResolverProvider(ABC):
    @abstractmethod
    def solve_image_captcha(self, image_bytes: bytes, source_host: str) -> str:
        raise NotImplementedError

