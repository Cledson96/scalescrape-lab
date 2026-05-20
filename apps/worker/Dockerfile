FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY packages/contracts ./packages/contracts
RUN pip install ./packages/contracts
COPY apps/worker/pyproject.toml .
RUN pip install . \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
COPY apps/worker/app ./app
COPY apps/worker/tools ./tools

CMD ["celery", "-A", "app.jobs.celery_app:celery_app", "worker", "--loglevel=INFO", "--pool=solo", "--concurrency=1", "-Q", "scrape.jobs,scrape.retry,scrape.captcha,scrape.dead_letter"]
