"""Deadlines run in UTC from the instant a turn or a battle opens. Nothing polls them."""

from datetime import datetime, timedelta

from hexcampaign.domain.errors import DomainError


def stamp(now: datetime) -> str:
    if now.tzinfo is None:
        raise DomainError("rules_invalid")
    return now.isoformat()


def overdue(opened: str | None, days: int, now: datetime) -> bool:
    if not opened:
        return False
    if now.tzinfo is None:
        raise DomainError("rules_invalid")
    return now >= datetime.fromisoformat(opened) + timedelta(days=days)
