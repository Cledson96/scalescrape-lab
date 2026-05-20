import logging

from celery import Celery
from celery.signals import worker_init
from kombu import Queue
from prometheus_client import start_http_server

from app.jobs.task_names import DEAD_LETTER_TASK, ENQUEUE_SCHEDULED_TASK, RUN_SCRAPE_TASK
from app.settings import settings

logger = logging.getLogger(__name__)
_metrics_server_started = False


def start_metrics_server_once(port: int = 9100) -> bool:
    global _metrics_server_started
    if _metrics_server_started:
        return False
    try:
        start_http_server(port)
    except OSError as exc:
        logger.warning("metricas_prometheus_indisponiveis port=%s error=%s", port, exc)
        return False
    _metrics_server_started = True
    return True


@worker_init.connect
def start_metrics_server_on_worker_start(**_kwargs) -> None:
    start_metrics_server_once()

celery_app = Celery("scalescrape_worker", broker=settings.rabbitmq_url)
celery_app.conf.task_default_queue = "scrape.jobs"
celery_app.conf.imports = ("app.jobs.tasks",)
celery_app.conf.task_queues = (
    Queue("scrape.jobs"),
    Queue("scrape.retry"),
    Queue("scrape.captcha"),
    Queue("scrape.dead_letter"),
)
celery_app.conf.task_routes = {
    RUN_SCRAPE_TASK: {"queue": "scrape.jobs"},
    DEAD_LETTER_TASK: {"queue": "scrape.dead_letter"},
    ENQUEUE_SCHEDULED_TASK: {"queue": "scrape.jobs"},
}
celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {}
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_soft_time_limit = max(1, settings.scraper_job_timeout_seconds - 10)
celery_app.conf.task_time_limit = settings.scraper_job_timeout_seconds

if settings.enable_scheduled_scraping:
    celery_app.conf.beat_schedule["scheduled-demo-scrapes-every-six-hours"] = {
        "task": ENQUEUE_SCHEDULED_TASK,
        "schedule": settings.scheduled_scrape_interval_seconds,
    }
