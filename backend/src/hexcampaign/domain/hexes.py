"""Axial hexes. This version of the map is a filled disk and nothing is impassable."""

import math
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Hex:
    q: int
    r: int


# Clockwise from the east. Pointy-top axial coordinates.
_STEPS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))

# The only disks the table generates: radius 2, 3 and 4.
DISK_RADIUS = {19: 2, 37: 3, 61: 4}


def neighbors(cell: Hex) -> tuple[Hex, ...]:
    return tuple(Hex(cell.q + step_q, cell.r + step_r) for step_q, step_r in _STEPS)


def distance(left: Hex, right: Hex) -> int:
    cube = abs(left.q + left.r - right.q - right.r)
    return (abs(left.q - right.q) + cube + abs(left.r - right.r)) // 2


def disk(size: int) -> tuple[Hex, ...]:
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
