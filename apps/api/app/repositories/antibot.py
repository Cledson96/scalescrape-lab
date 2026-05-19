from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import AntibotEvent


def list_recent_antibot_events(session: Session, limit: int = 100) -> list[AntibotEvent]:
    return list(session.scalars(select(AntibotEvent).order_by(desc(AntibotEvent.created_at)).limit(limit)))
