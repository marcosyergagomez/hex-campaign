"""In-process counters. The numbers die with the process; the log line stays."""

import logging
import threading
from collections import Counter

from api.request_id import current_request_id

log = logging.getLogger("hexcampaign.campaigns")

_lock = threading.Lock()
_counts: Counter[str] = Counter()

TURN_RESOLVED = "turn_resolved"
REVISION_CONFLICT = "revision_conflict"
UNHANDLED = "unhandled"


def note(event: str, *, request_id: str | None = None) -> None:
    with _lock:
        _counts[event] += 1
        count = _counts[event]
    identity = current_request_id() if request_id is None else request_id
    log.info("event=%s count=%s request_id=%s", event, count, identity)


def note_turn_resolved() -> None:
    note(TURN_RESOLVED)


def note_revision_conflict() -> None:
    note(REVISION_CONFLICT)


def note_unhandled(request_id: str) -> None:
    note(UNHANDLED, request_id=request_id)


def snapshot() -> dict[str, int]:
    with _lock:
        return dict(_counts)


def reset() -> None:
    with _lock:
        _counts.clear()
