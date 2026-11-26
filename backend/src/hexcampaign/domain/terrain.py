"""What a hex costs to leave, and how far an army looks while standing on it."""

from dataclasses import dataclass

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import Hex, neighbors

# Stable names. The battle rules do not care about the spelling on the map.
GROUNDS = frozenset(
    {
        "llanura",
        "colina",
        "bosque",
        "bosque_profundo",
        "montana",
        "montana_rocosa",
        "desierto",
        "tundra",
        "rio",
        "pantano",
        "lago",
        "playa",
        "acantilado",
        "mina",
        "campo",
    }
)
IMPASSABLE = frozenset({"montana_rocosa", "lago", "acantilado"})
_EXIT = {
    "llanura": 1,
    "colina": 2,
    "bosque": 2,
    "bosque_profundo": 3,
    "montana": 3,
    "desierto": 1,
    "tundra": 2,
    "rio": 3,
    "pantano": 3,
    "playa": 1,
    "mina": 1,
    "campo": 1,
}
_GAZE = {"colina": 3, "montana": 4, "bosque_profundo": 0}
_BASE_GAZE = 2
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


def gaze_from(plot: Plot | None) -> int:
    if plot is None:
        return _BASE_GAZE
    return _GAZE.get(plot.ground, _BASE_GAZE)


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
