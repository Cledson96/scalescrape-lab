from datetime import datetime, timedelta
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_session
from app.metrics import SCRAPE_JOBS_TOTAL, prometheus_response
from app.models import AntibotEvent, Job, JobEvent, ProxyProfile, Source
from app.schemas import JobCreate, JobRead, ProxyRead, SourceRead
from app.services.bootstrap import seed_defaults
from app.services.queue import enqueue_scrape_job

app = FastAPI(title="ScaleScrape Lab API", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    session = next(get_session())
    try:
        seed_defaults(session)
    finally:
        session.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return prometheus_response()


@app.post("/jobs", response_model=JobRead)
def create_job(payload: JobCreate, session: Session = Depends(get_session)) -> Job:
    source = session.scalar(select(Source).where(Source.name == payload.source))
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    if source.status != "active":
        raise HTTPException(status_code=409, detail=f"source_{source.status}")

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


@app.get("/jobs", response_model=list[JobRead])
def list_jobs(session: Session = Depends(get_session)) -> list[Job]:
    return list(session.scalars(select(Job).order_by(desc(Job.created_at)).limit(100)))


@app.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job


@app.post("/jobs/{job_id}/retry", response_model=JobRead)
def retry_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    job.status = "pending"
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


@app.get("/sources", response_model=list[SourceRead])
def list_sources(session: Session = Depends(get_session)) -> list[Source]:
    return list(session.scalars(select(Source).order_by(Source.name)))


@app.post("/sources/{source_id}/pause", response_model=SourceRead)
def pause_source(source_id: int, session: Session = Depends(get_session)) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    source.status = "paused"
    session.commit()
    return source


@app.post("/sources/{source_id}/resume", response_model=SourceRead)
def resume_source(source_id: int, session: Session = Depends(get_session)) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    source.status = "active"
    source.circuit_open_until = None
    session.commit()
    return source


@app.get("/proxies", response_model=list[ProxyRead])
def list_proxies(session: Session = Depends(get_session)) -> list[ProxyProfile]:
    return list(session.scalars(select(ProxyProfile).order_by(ProxyProfile.name)))


@app.post("/proxies/{proxy_id}/enable", response_model=ProxyRead)
def enable_proxy(proxy_id: int, session: Session = Depends(get_session)) -> ProxyProfile:
    proxy = session.get(ProxyProfile, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="proxy_not_found")
    proxy.status = "active"
    proxy.cooldown_until = None
    session.commit()
    return proxy


@app.post("/proxies/{proxy_id}/disable", response_model=ProxyRead)
def disable_proxy(proxy_id: int, session: Session = Depends(get_session)) -> ProxyProfile:
    proxy = session.get(ProxyProfile, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="proxy_not_found")
    proxy.status = "disabled"
    session.commit()
    return proxy


@app.post("/proxies/{proxy_id}/cooldown", response_model=ProxyRead)
def cooldown_proxy(proxy_id: int, session: Session = Depends(get_session)) -> ProxyProfile:
    proxy = session.get(ProxyProfile, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="proxy_not_found")
    proxy.status = "cooldown"
    proxy.cooldown_until = datetime.utcnow() + timedelta(minutes=5)
    session.commit()
    return proxy


@app.get("/antibot/events")
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

