from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import ProxyProfile
from app.schemas import ProxyRead
from app.services import proxies as proxy_service

router = APIRouter(tags=["Proxies"])


@router.get(
    "/proxies",
    response_model=list[ProxyRead],
    summary="Lista proxies cadastrados",
    description="Mostra os perfis de proxy conhecidos pelo laboratorio, incluindo status, concorrencia atual e cooldown.",
    response_description="Lista de proxies operacionais.",
)
def list_proxies(session: Session = Depends(get_session)) -> list[ProxyProfile]:
    return proxy_service.list_proxies(session)


@router.post(
    "/proxies/{proxy_id}/enable",
    response_model=ProxyRead,
    summary="Ativa um proxy",
    description="Coloca o proxy novamente em estado ativo e remove qualquer cooldown pendente.",
    response_description="Proxy atualizado com status ativo.",
    responses={404: {"description": "Proxy nao encontrado."}},
)
def enable_proxy(proxy_id: int, session: Session = Depends(get_session)) -> ProxyProfile:
    return proxy_service.enable_proxy(session, proxy_id)


@router.post(
    "/proxies/{proxy_id}/disable",
    response_model=ProxyRead,
    summary="Desabilita um proxy",
    description="Tira um proxy de circulacao manualmente, impedindo novas atribuicoes pelos workers.",
    response_description="Proxy atualizado com status desabilitado.",
    responses={404: {"description": "Proxy nao encontrado."}},
)
def disable_proxy(proxy_id: int, session: Session = Depends(get_session)) -> ProxyProfile:
    return proxy_service.disable_proxy(session, proxy_id)


@router.post(
    "/proxies/{proxy_id}/cooldown",
    response_model=ProxyRead,
    summary="Coloca um proxy em cooldown",
    description="Move o proxy para cooldown por 5 minutos, simulando protecao operacional apos falhas, bloqueios ou rate limit.",
    response_description="Proxy atualizado com status cooldown e horario limite.",
    responses={404: {"description": "Proxy nao encontrado."}},
)
def cooldown_proxy(proxy_id: int, session: Session = Depends(get_session)) -> ProxyProfile:
    return proxy_service.cooldown_proxy(session, proxy_id)
