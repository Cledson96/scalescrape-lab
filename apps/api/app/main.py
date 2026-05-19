from datetime import datetime, timedelta
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_session
from app.metrics import SCRAPE_JOBS_TOTAL, SCRAPE_SOURCE_CIRCUIT_OPEN, prometheus_response
from app.models import AntibotEvent, Job, JobEvent, ProxyProfile, ScrapedItem, Source
from app.schemas import JobCreate, JobRead, ProxyRead, ScrapedItemPageRead, ScrapedItemRead, SourceRead
from app.services.bootstrap import seed_defaults
from app.services.queue import enqueue_scrape_job
from app.settings import get_settings
from app.source_circuit import CIRCUIT_OPEN_SOURCE_STATUS, normalize_source_circuit

OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "Endpoints simples para verificar disponibilidade e prontidao basica da API.",
    },
    {
        "name": "Observability",
        "description": "Metricas Prometheus e visoes operacionais usadas para demonstrar monitoramento do laboratorio.",
    },
    {
        "name": "Jobs",
        "description": "Criacao, consulta e retry de jobs de scraping publicados na fila para os workers Celery/Playwright.",
    },
    {
        "name": "Items",
        "description": "Consulta de dados extraidos e persistidos no PostgreSQL, com filtros por job e paginacao por fonte.",
    },
    {
        "name": "Sources",
        "description": "Operacoes administrativas sobre as fontes de scraping, como pausa e reativacao.",
    },
    {
        "name": "Proxies",
        "description": "Controle operacional dos perfis de proxy usados pelos workers para distribuicao de carga e cooldown.",
    },
    {
        "name": "Anti-Bot",
        "description": "Eventos do simulador anti-bot e sinais usados para explicar bloqueios, risco e desafios de captcha.",
    },
]

APP_DESCRIPTION = """
API do laboratorio **ScaleScrape Lab**, criada para demonstrar um pipeline de scraping distribuido com foco em:

- orquestracao de jobs via FastAPI + RabbitMQ + Celery;
- scraping browser-first com Playwright;
- persistencia de jobs, eventos e itens extraidos em PostgreSQL;
- cenarios controlados de login, captcha, anti-bot, retry, timeout, cooldown e proxy rotation;
- observabilidade com Prometheus, Grafana e historico operacional.

## Como usar na demo

1. Crie um job em `POST /jobs` para uma fonte suportada.
2. O job e gravado no banco e publicado na fila dos workers.
3. Consulte o andamento em `GET /jobs` ou `GET /jobs/{job_id}`.
4. Leia os dados persistidos em `GET /items`, `GET /items/page` ou `GET /jobs/{job_id}/items`.
5. Se precisar, reenvie uma execucao com `POST /jobs/{job_id}/retry`.

## Fontes suportadas no laboratorio

- `fake-target`: target protegido com login, sessao, captcha e anti-bot local;
- `books-to-scrape`: catalogo publico usado para demonstrar normalizacao de preco, nota e descricao;
- `globo-home`: noticias publicas com enriquecimento de metadados e imagem;
- `betano-football`: odds reais usadas para demonstrar scraping de layout dinamico.

## Endpoints uteis

- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`
- Metricas Prometheus: `/metrics`
"""

app = FastAPI(
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
settings = get_settings()
Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    session = next(get_session())
    try:
        seed_defaults(session)
    finally:
        session.close()


@app.get(
    "/health",
    tags=["Health"],
    summary="Verifica a saude basica da API",
    description="Usado para readiness/liveness checks do container e para validacao rapida de disponibilidade da API.",
    response_description="Status simples indicando que a API respondeu com sucesso.",
)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/metrics",
    tags=["Observability"],
    summary="Expoe metricas Prometheus",
    description="Retorna metricas de jobs e operacao em formato Prometheus para scraping pelo Prometheus/Grafana.",
    response_description="Payload textual no formato Prometheus exposition.",
)
def metrics():
    return prometheus_response()


@app.post(
    "/jobs",
    response_model=JobRead,
    tags=["Jobs"],
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
    source = session.scalar(select(Source).where(Source.name == payload.source))
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    refresh_source_circuit(session, source)
    if source.status != "active":
        raise HTTPException(status_code=409, detail=source_unavailable_detail(source))

    job = Job(
        source_id=source.id,
        start_url=payload.start_url,
        mode=payload.mode,
        max_pages=payload.max_pages,
        status="pending",
    )
    session.add(job)
    session.flush()
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="job_created",
            message="Job criado pela API",
            metadata_json={"source": payload.source},
        )
    )
    session.commit()
    session.refresh(job)
    SCRAPE_JOBS_TOTAL.inc()
    enqueue_scrape_job(job.id)
    return job


@app.get(
    "/jobs",
    response_model=list[JobRead],
    tags=["Jobs"],
    summary="Lista jobs recentes",
    description="Retorna os ultimos 100 jobs ordenados do mais recente para o mais antigo, com status, tentativas e URL publica do alvo.",
    response_description="Lista de jobs recentes usados para auditoria e acompanhamento da fila.",
)
def list_jobs(session: Session = Depends(get_session)) -> list[Job]:
    return list(session.scalars(select(Job).order_by(desc(Job.created_at)).limit(100)))


@app.get(
    "/jobs/{job_id}",
    response_model=JobRead,
    tags=["Jobs"],
    summary="Consulta um job especifico",
    description="Recupera o estado atual de um job pelo identificador, incluindo status, quantidade de itens encontrados e horario de criacao.",
    response_description="Detalhes completos do job solicitado.",
    responses={404: {"description": "Job nao encontrado."}},
)
def get_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job


@app.get(
    "/items",
    response_model=list[ScrapedItemRead],
    tags=["Items"],
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
    query = select(ScrapedItem)
    if job_id is not None:
        query = query.where(ScrapedItem.job_id == job_id)
    query = query.order_by(desc(ScrapedItem.created_at)).limit(limit)
    return list(session.scalars(query))


@app.get(
    "/items/page",
    response_model=ScrapedItemPageRead,
    tags=["Items"],
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
    filters = []
    if source:
        filters.append(Source.name == source)

    count_query = select(func.count(ScrapedItem.id)).join(Job).join(Source)
    item_query = select(ScrapedItem).join(Job).join(Source)
    if filters:
        count_query = count_query.where(*filters)
        item_query = item_query.where(*filters)

    total = session.scalar(count_query) or 0
    items = list(
        session.scalars(
            item_query.order_by(desc(ScrapedItem.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return ScrapedItemPageRead(items=items, total=total, page=page, page_size=page_size)


@app.get(
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
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    query = (
        select(ScrapedItem)
        .where(ScrapedItem.job_id == job_id)
        .order_by(desc(ScrapedItem.created_at))
        .limit(limit)
    )
    return list(session.scalars(query))


@app.post(
    "/jobs/{job_id}/retry",
    response_model=JobRead,
    tags=["Jobs"],
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
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    refresh_source_circuit(session, job.source)
    if job.source.status != "active":
        raise HTTPException(status_code=409, detail=source_unavailable_detail(job.source))
    job.status = "pending"
    job.attempts = 0
    job.error_message = None
    job.finished_at = None
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="job_retry_requested",
            message="Retry manual solicitado",
        )
    )
    session.commit()
    enqueue_scrape_job(job.id)
    return job


@app.get(
    "/sources",
    response_model=list[SourceRead],
    tags=["Sources"],
    summary="Lista fontes cadastradas",
    description="Retorna as fontes conhecidas pela API com status atual e eventual abertura de circuito.",
    response_description="Lista de fontes configuradas para scraping.",
)
def list_sources(session: Session = Depends(get_session)) -> list[Source]:
    sources = list(session.scalars(select(Source).order_by(Source.name)))
    changed = False
    for source in sources:
        state = refresh_source_circuit(session, source)
        changed = changed or state.closed_after_expiry
    if changed:
        session.commit()
    return sources


@app.post(
    "/sources/{source_id}/pause",
    response_model=SourceRead,
    tags=["Sources"],
    summary="Pausa uma fonte",
    description="Marca a fonte como pausada para impedir criacao de novos jobs daquela origem ate nova liberacao manual.",
    response_description="Fonte atualizada com status pausado.",
    responses={404: {"description": "Fonte nao encontrada."}},
)
def pause_source(source_id: int, session: Session = Depends(get_session)) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    source.status = "paused"
    source.circuit_open_until = None
    session.commit()
    return source


@app.post(
    "/sources/{source_id}/resume",
    response_model=SourceRead,
    tags=["Sources"],
    summary="Reativa uma fonte",
    description="Restaura a fonte para status ativo e limpa eventual abertura de circuito antes de novas execucoes.",
    response_description="Fonte reativada e pronta para novos jobs.",
    responses={404: {"description": "Fonte nao encontrada."}},
)
def resume_source(source_id: int, session: Session = Depends(get_session)) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    source.status = "active"
    source.circuit_open_until = None
    session.commit()
    return source


@app.get(
    "/proxies",
    response_model=list[ProxyRead],
    tags=["Proxies"],
    summary="Lista proxies cadastrados",
    description="Mostra os perfis de proxy conhecidos pelo laboratorio, incluindo status, concorrencia atual e cooldown.",
    response_description="Lista de proxies operacionais.",
)
def list_proxies(session: Session = Depends(get_session)) -> list[ProxyProfile]:
    return list(session.scalars(select(ProxyProfile).order_by(ProxyProfile.name)))


@app.post(
    "/proxies/{proxy_id}/enable",
    response_model=ProxyRead,
    tags=["Proxies"],
    summary="Ativa um proxy",
    description="Coloca o proxy novamente em estado ativo e remove qualquer cooldown pendente.",
    response_description="Proxy atualizado com status ativo.",
    responses={404: {"description": "Proxy nao encontrado."}},
)
def enable_proxy(proxy_id: int, session: Session = Depends(get_session)) -> ProxyProfile:
    proxy = session.get(ProxyProfile, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="proxy_not_found")
    proxy.status = "active"
    proxy.cooldown_until = None
    session.commit()
    return proxy


@app.post(
    "/proxies/{proxy_id}/disable",
    response_model=ProxyRead,
    tags=["Proxies"],
    summary="Desabilita um proxy",
    description="Tira um proxy de circulacao manualmente, impedindo novas atribuicoes pelos workers.",
    response_description="Proxy atualizado com status desabilitado.",
    responses={404: {"description": "Proxy nao encontrado."}},
)
def disable_proxy(proxy_id: int, session: Session = Depends(get_session)) -> ProxyProfile:
    proxy = session.get(ProxyProfile, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="proxy_not_found")
    proxy.status = "disabled"
    session.commit()
    return proxy


@app.post(
    "/proxies/{proxy_id}/cooldown",
    response_model=ProxyRead,
    tags=["Proxies"],
    summary="Coloca um proxy em cooldown",
    description="Move o proxy para cooldown por 5 minutos, simulando protecao operacional apos falhas, bloqueios ou rate limit.",
    response_description="Proxy atualizado com status cooldown e horario limite.",
    responses={404: {"description": "Proxy nao encontrado."}},
)
def cooldown_proxy(proxy_id: int, session: Session = Depends(get_session)) -> ProxyProfile:
    proxy = session.get(ProxyProfile, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="proxy_not_found")
    proxy.status = "cooldown"
    proxy.cooldown_until = datetime.utcnow() + timedelta(minutes=5)
    session.commit()
    return proxy


@app.get(
    "/antibot/events",
    tags=["Anti-Bot", "Observability"],
    summary="Lista eventos recentes do simulador anti-bot",
    description=(
        "Retorna ate 100 eventos recentes do simulador anti-bot, incluindo sessao, proxy, acao tomada, motivo e score de risco. "
        "E util para explicar por que uma sessao foi liberada, desafiada, atrasada ou bloqueada."
    ),
    response_description="Eventos recentes do simulador anti-bot em formato JSON.",
)
def list_antibot_events(session: Session = Depends(get_session)) -> list[dict]:
    events = session.scalars(
        select(AntibotEvent).order_by(desc(AntibotEvent.created_at)).limit(100)
    )
    return [
        {
            "id": event.id,
            "session_id": event.session_id,
            "proxy_id": event.proxy_id,
            "risk_score": event.risk_score,
            "action": event.action,
            "reason": event.reason,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]


def refresh_source_circuit(session: Session, source: Source):
    state = normalize_source_circuit(source.status, source.circuit_open_until)
    if state.closed_after_expiry:
        source.status = state.status
        source.circuit_open_until = state.circuit_open_until
        session.flush()
    SCRAPE_SOURCE_CIRCUIT_OPEN.labels(source=source.name).set(
        1 if source.status == CIRCUIT_OPEN_SOURCE_STATUS else 0
    )
    return state


def source_unavailable_detail(source: Source) -> dict[str, str | None]:
    if source.status == CIRCUIT_OPEN_SOURCE_STATUS:
        return {
            "reason": "source_circuit_open",
            "source": source.name,
            "circuit_open_until": (
                source.circuit_open_until.isoformat() if source.circuit_open_until else None
            ),
        }
    return {
        "reason": f"source_{source.status}",
        "source": source.name,
        "circuit_open_until": None,
    }

