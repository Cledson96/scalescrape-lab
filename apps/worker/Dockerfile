FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app
COPY packages/contracts ./packages/contracts
RUN pip install --no-cache-dir ./packages/contracts
COPY apps/worker/pyproject.toml .
RUN pip install --no-cache-dir .
COPY apps/worker/app ./app
COPY apps/worker/tools ./tools

CMD ["celery", "-A", "app.jobs.celery_app:celery_app", "worker", "--loglevel=INFO", "--pool=solo", "--concurrency=1", "-Q", "scrape.jobs,scrape.retry,scrape.captcha"]
