FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app ./app
COPY test_betano.py .

CMD ["celery", "-A", "app.celery_app:celery_app", "worker", "--loglevel=INFO", "--pool=solo", "--concurrency=1", "-Q", "scrape.jobs,scrape.retry,scrape.captcha"]
