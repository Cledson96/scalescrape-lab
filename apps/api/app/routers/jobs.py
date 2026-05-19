from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Job
from app.schemas import JobCreate, JobRead
from app.services import jobs as job_service

router = APIRouter(tags=["Jobs"])


@router.post(
    "/jobs",
    response_model=JobRead,
    summary="Cria um novo job de scraping",
    description=(
        "Cria um job pendente para uma fonte suportada, registra um evento operacional no banco e publica a execucao "
        "na fila consumida pelos workers. E o endpoint principal para iniciar uma coleta pela API."
    ),
    response_description="Job criado e enfileirado com os dados persistidos no banco.",
    responses={
        404: {"description": "Fonte informada nao existe."},
        409: {"description": "Fonte encontrada, mas pausada ou indisponivel para execucao."},
    },
)
def create_job(payload: JobCreate, session: Session = Depends(get_session)) -> Job:
    return job_service.create_scrape_job(session, payload)


@router.get(
    "/jobs",
    response_model=list[JobRead],
    summary="Lista jobs recentes",
    description="Retorna os ultimos 100 jobs ordenados do mais recente para o mais antigo, com status, tentativas e URL publica do alvo.",
    response_description="Lista de jobs recentes usados para auditoria e acompanhamento da fila.",
)
def list_jobs(session: Session = Depends(get_session)) -> list[Job]:
    return job_service.list_recent_jobs(session)


@router.get(
    "/jobs/{job_id}",
    response_model=JobRead,
    summary="Consulta um job especifico",
    description="Recupera o estado atual de um job pelo identificador, incluindo status, quantidade de itens encontrados e horario de criacao.",
    response_description="Detalhes completos do job solicitado.",
    responses={404: {"description": "Job nao encontrado."}},
)
def get_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    return job_service.get_job(session, job_id)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobRead,
    summary="Solicita retry manual de um job",
    description=(
        "Reabre um job existente, limpa erro e horario de finalizacao e publica novamente a execucao na fila. "
        "Util quando a demo precisa mostrar retry apos bloqueio, falha tecnica ou ajuste operacional."
    ),
    response_description="Job reaberto com status pendente e reenviado para processamento.",
    responses={
        404: {"description": "Job nao encontrado."},
        409: {"description": "Fonte do job esta pausada ou com circuito aberto."},
    },
)
def retry_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    return job_service.retry_scrape_job(session, job_id)
