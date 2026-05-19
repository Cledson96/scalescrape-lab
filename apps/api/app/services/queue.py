from celery import Celery

from app.settings import get_settings

RUN_SCRAPE_TASK = "app.jobs.tasks.run_scrape_job"


def make_celery() -> Celery:
    settings = get_settings()
    celery = Celery("scalescrape_api", broker=settings.rabbitmq_url)
    celery.conf.task_default_queue = "scrape.jobs"
    return celery


celery_app = make_celery()


def enqueue_scrape_job(job_id: int) -> None:
    celery_app.send_task(RUN_SCRAPE_TASK, args=[job_id], queue="scrape.jobs")

