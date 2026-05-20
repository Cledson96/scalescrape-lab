from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.captcha.mock_provider import MockCaptchaResolverProvider
from app.captcha.two_captcha_provider import TwoCaptchaConfig, TwoCaptchaImageResolverProvider
from app.proxy.manager import default_proxy_manager
from app.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

proxy_manager = default_proxy_manager(
    max_concurrent_jobs=settings.max_concurrent_jobs_per_proxy,
    cooldown_seconds=settings.proxy_cooldown_seconds,
    enable_rotation=settings.enable_proxy_rotation,
)


def make_captcha_provider():
    if settings.enable_real_2captcha:
        return TwoCaptchaImageResolverProvider(
            TwoCaptchaConfig(
                api_key=settings.two_captcha_api_key,
                allowed_hosts=settings.allowed_captcha_hosts,
                enabled=True,
                max_solves_per_run=settings.max_captcha_solves_per_run,
            )
        )
    return MockCaptchaResolverProvider(answer=settings.target_site_fixed_captcha_answer)
