"""Army and explorer tokens share one list; only armies fight and hold forts."""

from typing import Protocol

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.terrain import Plot, gaze_from

KINDS = frozenset({"army", "explorer"})
EXPLORER_MOVE_BONUS = 2
EXPLORER_GAZE_BONUS = 1


class _Kinded(Protocol):
    kind: str


def checked_kind(value: object) -> str:
    if not isinstance(value, str) or value not in KINDS:
        raise DomainError("rules_invalid")
    return value


def is_fighter(army: _Kinded) -> bool:
    return army.kind == "army"


def is_explorer(army: _Kinded) -> bool:
    return army.kind == "explorer"


def move_budget(movement: int, army: _Kinded) -> int:
    return movement + (EXPLORER_MOVE_BONUS if is_explorer(army) else 0)


def unit_gaze(army: _Kinded, plot: Plot | None) -> int:
    return gaze_from(plot) + (EXPLORER_GAZE_BONUS if is_explorer(army) else 0)
