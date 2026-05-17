from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class AntibotAction(str, Enum):
    ALLOW = "allow"
    DELAY = "delay"
    CHALLENGE = "challenge"
    FORBID = "forbid"
    RATE_LIMIT = "rate_limit"


@dataclass
class Visit:
    path: str
    created_at: datetime


@dataclass
class SessionState:
    session_id: str
    proxy_id: str
    visits: list[Visit] = field(default_factory=list)
    captcha_errors: int = 0
    saw_listing: bool = False


@dataclass(frozen=True)
class AntibotDecision:
    risk_score: int
    action: AntibotAction
    reason: str


class AntibotSimulator:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionState] = {}

    def get_state(self, session_id: str, proxy_id: str) -> SessionState:
        key = f"{proxy_id}:{session_id}"
        if key not in self.sessions:
            self.sessions[key] = SessionState(session_id=session_id, proxy_id=proxy_id)
        return self.sessions[key]

    def record_captcha_error(self, session_id: str, proxy_id: str) -> None:
        state = self.get_state(session_id, proxy_id)
        state.captcha_errors += 1

    def evaluate(
        self,
        *,
        session_id: str,
        proxy_id: str,
        path: str,
        user_agent: str | None,
        has_clearance_cookie: bool,
        now: datetime | None = None,
    ) -> AntibotDecision:
        current_time = now or datetime.utcnow()
        state = self.get_state(session_id, proxy_id)
        state.visits = [
            visit for visit in state.visits if visit.created_at > current_time - timedelta(minutes=1)
        ]
        state.visits.append(Visit(path=path, created_at=current_time))

        if path.startswith("/items"):
            state.saw_listing = True

        score = 0
        reasons: list[str] = []

        if len(state.visits) >= 12:
            return AntibotDecision(95, AntibotAction.RATE_LIMIT, "muitas requisicoes em 1 minuto")

        if len(state.visits) >= 7:
            score += 35
            reasons.append("volume alto por minuto")

        if not has_clearance_cookie:
            score += 20
            reasons.append("sem cookie de sessao liberada")

        if not user_agent or "bot" in user_agent.lower():
            score += 20
            reasons.append("user-agent ausente ou suspeito")

        if path.startswith("/items/") and not state.saw_listing:
            score += 25
            reasons.append("acesso direto ao detalhe")

        if state.captcha_errors:
            score += min(30, state.captcha_errors * 15)
            reasons.append("erros de captcha anteriores")

        score = min(score, 100)
        reason = ", ".join(reasons) or "baixo risco"

        if score < 40:
            return AntibotDecision(score, AntibotAction.ALLOW, reason)
        if score < 70:
            return AntibotDecision(score, AntibotAction.DELAY, reason)
        if score < 90:
            return AntibotDecision(score, AntibotAction.CHALLENGE, reason)
        return AntibotDecision(score, AntibotAction.FORBID, reason)

