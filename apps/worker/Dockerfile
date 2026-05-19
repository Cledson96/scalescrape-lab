FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app ./app
COPY tools ./tools

CMD ["celery", "-A", "app.jobs.celery_app:celery_app", "worker", "--loglevel=INFO", "--pool=solo", "--concurrency=1", "-Q", "scrape.jobs,scrape.retry,scrape.captcha"]
