from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Source
from app.schemas import SourceRead
from app.services import sources as source_service

router = APIRouter(tags=["Sources"])


@router.get(
    "/sources",
    response_model=list[SourceRead],
    summary="Lista fontes cadastradas",
    description="Retorna as fontes conhecidas pela API com status atual e eventual abertura de circuito.",
    response_description="Lista de fontes configuradas para scraping.",
)
def list_sources(session: Session = Depends(get_session)) -> list[Source]:
    return source_service.list_sources(session)


@router.post(
    "/sources/{source_id}/pause",
    response_model=SourceRead,
    summary="Pausa uma fonte",
    description="Marca a fonte como pausada para impedir criacao de novos jobs daquela origem ate nova liberacao manual.",
    response_description="Fonte atualizada com status pausado.",
    responses={404: {"description": "Fonte nao encontrada."}},
)
def pause_source(source_id: int, session: Session = Depends(get_session)) -> Source:
    return source_service.pause_source(session, source_id)


@router.post(
    "/sources/{source_id}/resume",
    response_model=SourceRead,
    summary="Reativa uma fonte",
    description="Restaura a fonte para status ativo e limpa eventual abertura de circuito antes de novas execucoes.",
    response_description="Fonte reativada e pronta para novos jobs.",
    responses={404: {"description": "Fonte nao encontrada."}},
)
def resume_source(source_id: int, session: Session = Depends(get_session)) -> Source:
    return source_service.resume_source(session, source_id)
