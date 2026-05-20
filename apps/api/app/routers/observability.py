from fastapi import APIRouter

from app.metrics import prometheus_response

router = APIRouter(tags=["Observability"])


@router.get(
    "/metrics",
    summary="Expoe metricas Prometheus",
    description="Retorna metricas de jobs e operacao em formato Prometheus para scraping pelo Prometheus/Grafana.",
    response_description="Payload textual no formato Prometheus exposition.",
)
def metrics():
    return prometheus_response()
