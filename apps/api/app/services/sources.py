from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.metrics import SCRAPE_SOURCE_CIRCUIT_OPEN
from app.models import Source
from app.repositories import sources as source_repository
from app.services.source_circuit import CIRCUIT_OPEN_SOURCE_STATUS, normalize_source_circuit


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


def ensure_source_available(session: Session, source: Source) -> None:
    refresh_source_circuit(session, source)
    if source.status != "active":
        raise ConflictError(source_unavailable_detail(source))


def list_sources(session: Session) -> list[Source]:
    sources = source_repository.list_sources(session)
    changed = False
    for source in sources:
        state = refresh_source_circuit(session, source)
        changed = changed or state.closed_after_expiry
    if changed:
        session.commit()
    return sources


def pause_source(session: Session, source_id: int) -> Source:
    source = source_repository.get_source(session, source_id)
    if source is None:
        raise NotFoundError("source_not_found")
    source.status = "paused"
    source.circuit_open_until = None
    session.commit()
    return source


def resume_source(session: Session, source_id: int) -> Source:
    source = source_repository.get_source(session, source_id)
    if source is None:
        raise NotFoundError("source_not_found")
    source.status = "active"
    source.circuit_open_until = None
    session.commit()
    return source
