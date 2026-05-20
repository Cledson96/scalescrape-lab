from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from scalescrape_contracts.clock import utc_now_naive

ACTIVE_SOURCE_STATUS = "active"
CIRCUIT_OPEN_SOURCE_STATUS = "circuit_open"
CIRCUIT_FAILURE_OUTCOMES = {"blocked", "rate_limited", "timeout", "dead_lettered", "failed"}


@dataclass(frozen=True)
class SourceCircuitState:
    status: str
    circuit_open_until: datetime | None
    closed_after_expiry: bool = False


def normalize_source_circuit(
    status: str,
    circuit_open_until: datetime | None,
    now: datetime | None = None,
) -> SourceCircuitState:
    current = now or utc_now_naive()
    if status == CIRCUIT_OPEN_SOURCE_STATUS and circuit_open_until and circuit_open_until <= current:
        return SourceCircuitState(ACTIVE_SOURCE_STATUS, None, closed_after_expiry=True)
    return SourceCircuitState(status, circuit_open_until)


def source_accepts_new_jobs(status: str, circuit_open_until: datetime | None, now: datetime | None = None) -> bool:
    state = normalize_source_circuit(status, circuit_open_until, now)
    return state.status == ACTIVE_SOURCE_STATUS


def should_open_source_circuit(recent_outcomes: Iterable[str], failure_threshold: int) -> bool:
    threshold = max(1, failure_threshold)
    failures = [outcome for outcome in recent_outcomes if outcome in CIRCUIT_FAILURE_OUTCOMES]
    return len(failures) >= threshold


def next_source_circuit_deadline(cooldown_seconds: int, now: datetime | None = None) -> datetime:
    return (now or utc_now_naive()) + timedelta(seconds=max(1, cooldown_seconds))
