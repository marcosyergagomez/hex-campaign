"""Axial hexes. A plain campaign uses a disk of 19, 37 or 61. A terrain map uses a larger one."""

import math
from dataclasses import dataclass

from hexcampaign.domain.errors import DomainError


@dataclass(frozen=True, order=True)
class Hex:
    q: int
    r: int


# Clockwise from the east. Pointy-top axial coordinates.
_STEPS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))

TABLE_RADII = (9, 11, 13)
# Saved coordinates are bounded to +/-64.
DISK_RADIUS = {1 + 3 * radius * (radius + 1): radius for radius in range(2, 65)}


def deploy_reach(map_size: int) -> int:
    """How many hexes from the keep a piece may stand: one, two, or three by table size."""
    radius = DISK_RADIUS.get(map_size)
    if radius is None or radius <= TABLE_RADII[0]:
        return 1
    if radius <= TABLE_RADII[1]:
        return 2
    return 3


def neighbors(cell: Hex) -> tuple[Hex, ...]:
    return tuple(Hex(cell.q + step_q, cell.r + step_r) for step_q, step_r in _STEPS)


def distance(left: Hex, right: Hex) -> int:
    cube = abs(left.q + left.r - right.q - right.r)
    return (abs(left.q - right.q) + cube + abs(left.r - right.r)) // 2


def disk(size: int) -> tuple[Hex, ...]:
    if type(size) is not int or size not in DISK_RADIUS:
        raise DomainError("rules_invalid")
    radius = DISK_RADIUS[size]
    cells = [
        Hex(q, r)
        for q in range(-radius, radius + 1)
        for r in range(-radius, radius + 1)
        if distance(Hex(q, r), Hex(0, 0)) <= radius
    ]
    cells.sort()
    return tuple(cells)


def angle(cell: Hex) -> float:
    flat = 1.5 * cell.q
    rise = math.sqrt(3) * (cell.r + cell.q / 2)
    return math.atan2(rise, flat)
