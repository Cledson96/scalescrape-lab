from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import ScrapedItem
from app.schemas import ScrapedItemPageRead, ScrapedItemRead
from app.services import items as item_service

router = APIRouter(tags=["Items"])


@router.get(
    "/items",
    response_model=list[ScrapedItemRead],
    summary="Lista itens extraidos",
    description=(
        "Consulta itens persistidos no banco, opcionalmente filtrando por `job_id`. Ideal para validacao rapida do ultimo scraping "
        "ou inspeção do payload bruto normalizado em `raw_data`."
    ),
    response_description="Lista de itens extraidos ordenados do mais recente para o mais antigo.",
)
def list_items(
    job_id: int | None = Query(default=None, description="Filtra apenas os itens gerados por um job especifico."),
    limit: int = Query(default=100, ge=1, le=500, description="Quantidade maxima de itens retornados."),
    session: Session = Depends(get_session),
) -> list[ScrapedItem]:
    return item_service.list_items(session, job_id, limit)


@router.get(
    "/items/page",
    response_model=ScrapedItemPageRead,
    summary="Lista itens paginados por fonte",
    description=(
        "Endpoint usado pelo dashboard visual para exibir uma tabela por fonte. Permite filtrar por nome da fonte e navegar "
        "por pagina mantendo total, pagina atual e total de paginas."
    ),
    response_description="Pagina de itens com metadata de totalizacao.",
)
def list_items_page(
    source: str | None = Query(default=None, description="Nome da fonte, como `fake-target`, `books-to-scrape`, `globo-home` ou `betano-football`."),
    page: int = Query(default=1, ge=1, description="Numero da pagina a ser retornada."),
    page_size: int = Query(default=10, ge=1, le=50, description="Quantidade de itens por pagina."),
    session: Session = Depends(get_session),
) -> ScrapedItemPageRead:
    return item_service.list_items_page(session, source, page, page_size)


@router.get(
    "/jobs/{job_id}/items",
    response_model=list[ScrapedItemRead],
    tags=["Items", "Jobs"],
    summary="Lista itens de um job especifico",
    description="Retorna apenas os itens produzidos por um job, mantendo a ordenacao do mais recente para o mais antigo.",
    response_description="Lista de itens relacionados ao job informado.",
    responses={404: {"description": "Job nao encontrado."}},
)
def list_job_items(
    job_id: int,
    limit: int = Query(default=100, ge=1, le=500, description="Quantidade maxima de itens retornados para o job."),
    session: Session = Depends(get_session),
) -> list[ScrapedItem]:
    return item_service.list_job_items(session, job_id, limit)
