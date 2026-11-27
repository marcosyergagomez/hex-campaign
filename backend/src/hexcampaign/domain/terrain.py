"""What a hex costs to leave, and how far an army looks while standing on it."""

import json
from dataclasses import dataclass
from pathlib import Path

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import Hex, neighbors


def _contract() -> dict:
    """The exit table lives once, in shared/terrain.json, and the client reads it too."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        path = parent / "shared" / "terrain.json"
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
            break
    raise RuntimeError("shared/terrain.json is missing or unreadable")


def _names(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"shared/terrain.json {label} must list names")
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item or item in names:
            raise RuntimeError(f"shared/terrain.json {label} has a bad name")
        names.append(item)
    return tuple(names)


def _whole(value: object, label: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RuntimeError(f"shared/terrain.json {label} must be a whole number")
    return value


def _table(value: object, label: str, *, minimum: int) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise RuntimeError(f"shared/terrain.json {label} is missing")
    table: dict[str, int] = {}
    for name, cost in value.items():
        if not isinstance(name, str) or not name:
            raise RuntimeError(f"shared/terrain.json {label} has a bad name")
        table[name] = _whole(cost, label, minimum=minimum)
    return table


_RAW = _contract()
# Stable names. The battle rules do not care about the spelling on the map.
GROUNDS = frozenset(_names(_RAW.get("grounds"), "grounds"))
IMPASSABLE = frozenset(_names(_RAW.get("impassable"), "impassable"))
_EXIT = _table(_RAW.get("exit"), "exit", minimum=1)
_GAZE = _table(_RAW.get("gaze"), "gaze", minimum=0)
_BASE_GAZE = _whole(_RAW.get("base_gaze"), "base_gaze", minimum=0)
OPEN_GROUNDS = frozenset(_names(_RAW.get("open_grounds"), "open_grounds"))
EXPLORER_MOVE_BONUS = _whole(_RAW.get("explorer_move_bonus"), "explorer_move_bonus", minimum=0)
EXPLORER_GAZE_BONUS = _whole(_RAW.get("explorer_gaze_bonus"), "explorer_gaze_bonus", minimum=0)
if not IMPASSABLE <= GROUNDS or not OPEN_GROUNDS <= GROUNDS or not set(_GAZE) <= GROUNDS:
    raise RuntimeError("shared/terrain.json names a ground outside grounds")
if set(_EXIT) != GROUNDS - IMPASSABLE:
    raise RuntimeError("shared/terrain.json exit table must cover every passable ground")
HOME_RADIUS = {19: 1, 37: 1, 61: 2, 271: 2, 397: 2, 547: 3, 817: 4}


@dataclass(frozen=True)
class Plot:
    ground: str
    road: bool = False
    bridge: bool = False


def checked_plot(ground: object, road: object, bridge: object) -> Plot:
    # Legacy maps may still store "orilla"; keep bridges on river, the rest as plain.
    if ground == "orilla":
        ground = "rio" if bridge is True else "llanura"
    if not isinstance(ground, str) or ground not in GROUNDS:
        raise DomainError("rules_invalid")
    if not isinstance(road, bool) or not isinstance(bridge, bool):
        raise DomainError("rules_invalid")
    if ground in IMPASSABLE and (road or bridge):
        raise DomainError("rules_invalid")
    if bridge and ground != "rio":
        raise DomainError("rules_invalid")
    return Plot(ground, road, bridge)


def passable(plot: Plot) -> bool:
    return plot.ground not in IMPASSABLE


def exit_cost(plot: Plot) -> int:
    """Points to leave this hex. A road or a bridge makes that exit cost 1."""
    if plot.road or plot.bridge:
        return 1
    return _EXIT[plot.ground]


def road_refund(plot: Plot) -> int:
    """A road on rough ground returns one point after the exit is paid."""
    if plot.road and plot.ground not in OPEN_GROUNDS:
        return 1
    return 0


def gaze_from(plot: Plot | None) -> int:
    if plot is None:
        return _BASE_GAZE
    return _GAZE.get(plot.ground, _BASE_GAZE)


def has_terrain(game) -> bool:
    """True when the campaign document carries a terrain atlas."""
    return getattr(game, "plots", None) is not None


def terrain_groups(plots: dict[Hex, Plot], grounds: set[str] | frozenset[str]) -> list[set[Hex]]:
    pending = {cell for cell, plot in plots.items() if plot.ground in grounds}
    groups: list[set[Hex]] = []
    while pending:
        start = min(pending)
        pending.remove(start)
        group = {start}
        queue = [start]
        while queue:
            cell = queue.pop()
            for other in neighbors(cell):
                if other in pending:
                    pending.remove(other)
                    group.add(other)
                    queue.append(other)
        groups.append(group)
    return groups
