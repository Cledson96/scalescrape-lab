from celery import Celery
from prometheus_client import start_http_server

from app.settings import settings

start_http_server(9100)

celery_app = Celery("scalescrape_worker", broker=settings.rabbitmq_url)
celery_app.conf.task_default_queue = "scrape.jobs"
celery_app.conf.imports = ("app.tasks",)
celery_app.conf.task_routes = {
    "app.tasks.run_scrape_job": {"queue": "scrape.jobs"},
    "app.tasks.enqueue_scheduled_scrape_jobs": {"queue": "scrape.jobs"},
}
celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {}

if settings.enable_scheduled_scraping:
    celery_app.conf.beat_schedule["scheduled-demo-scrapes-every-six-hours"] = {
        "task": "app.tasks.enqueue_scheduled_scrape_jobs",
        "schedule": settings.scheduled_scrape_interval_seconds,
    }
