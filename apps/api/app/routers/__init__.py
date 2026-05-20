from fastapi import APIRouter

from app.routers.antibot import router as antibot_router
from app.routers.health import router as health_router
from app.routers.items import router as items_router
from app.routers.jobs import router as jobs_router
from app.routers.observability import router as observability_router
from app.routers.proxies import router as proxies_router
from app.routers.sources import router as sources_router

api_routers: tuple[APIRouter, ...] = (
    health_router,
    observability_router,
    jobs_router,
    items_router,
    sources_router,
    proxies_router,
    antibot_router,
)

__all__ = ["api_routers"]
