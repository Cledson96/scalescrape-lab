from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

SCRAPE_JOBS_TOTAL = Counter("scrape_jobs_total", "Total de jobs criados")
SCRAPE_JOB_DURATION = Histogram(
    "scrape_job_duration_seconds", "Duracao dos jobs de scraping"
)
SCRAPE_WORKER_ACTIVE_JOBS = Gauge(
    "scrape_worker_active_jobs", "Jobs ativos reportados pelos workers"
)
SCRAPE_SOURCE_CIRCUIT_OPEN = Gauge(
    "scrape_source_circuit_open", "Circuit breaker aberto por fonte", ["source"]
)


def prometheus_response() -> Response:
    return Response(generate_latest(), media_type="text/plain; version=0.0.4")

