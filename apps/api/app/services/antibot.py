from sqlalchemy.orm import Session

from app.repositories import antibot as antibot_repository


def list_antibot_events(session: Session) -> list[dict]:
    events = antibot_repository.list_recent_antibot_events(session)
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
