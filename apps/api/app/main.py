from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api_metadata import APP_DESCRIPTION, OPENAPI_TAGS
from app.database import SessionLocal
from app.errors import ApiError
from app.routers import api_routers
from app.services.bootstrap import seed_defaults
from app.settings import get_settings


def create_app() -> FastAPI:
    application = FastAPI(
        title="ScaleScrape Lab API",
        summary="Orquestracao, consulta e observabilidade de um laboratorio de scraping distribuido.",
        description=APP_DESCRIPTION,
        version="0.1.0",
        contact={
            "name": "ScaleScrape Lab",
            "url": "https://dev.scalescrape.cledson.com.br/dashboard",
        },
        openapi_tags=OPENAPI_TAGS,
    )
    register_error_handlers(application)
    register_routes(application)
    mount_media(application)
    return application


def register_routes(application: FastAPI) -> None:
    for router in api_routers:
        application.include_router(router)


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def mount_media(application: FastAPI) -> None:
    settings = get_settings()
    Path(settings.media_root).mkdir(parents=True, exist_ok=True)
    application.mount("/media", StaticFiles(directory=settings.media_root), name="media")


app = create_app()


@app.on_event("startup")
def on_startup() -> None:
    with SessionLocal() as session:
        seed_defaults(session)
