from __future__ import annotations

import random

RETRYABLE_OUTCOMES = {"blocked", "rate_limited", "failed", "timeout"}


def normalized_max_attempts(max_attempts: int) -> int:
    return max(1, max_attempts)


def should_retry_outcome(outcome: str, attempt: int, max_attempts: int) -> bool:
    return outcome in RETRYABLE_OUTCOMES and attempt < normalized_max_attempts(max_attempts)


def status_after_retryable_failure(outcome: str, attempt: int, max_attempts: int) -> str:
    if should_retry_outcome(outcome, attempt, max_attempts):
        return "retrying"
    if outcome in RETRYABLE_OUTCOMES:
        return "dead_lettered"
    return outcome


def retry_countdown_seconds(
    attempt: int,
    *,
    base_seconds: int = 30,
    max_seconds: int = 300,
    jitter_seconds: int = 10,
) -> int:
    exponential_delay = base_seconds * (2 ** max(0, attempt - 1))
    capped_delay = min(max_seconds, exponential_delay)
    if jitter_seconds <= 0:
        return capped_delay
    return capped_delay + random.randint(0, jitter_seconds)
