from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.services import antibot as antibot_service

router = APIRouter(tags=["Anti-Bot", "Observability"])


@router.get(
    "/antibot/events",
    summary="Lista eventos recentes do simulador anti-bot",
    description=(
        "Retorna ate 100 eventos recentes do simulador anti-bot, incluindo sessao, proxy, acao tomada, motivo e score de risco. "
        "E util para explicar por que uma sessao foi liberada, desafiada, atrasada ou bloqueada."
    ),
    response_description="Eventos recentes do simulador anti-bot em formato JSON.",
)
def list_antibot_events(session: Session = Depends(get_session)) -> list[dict]:
    return antibot_service.list_antibot_events(session)
