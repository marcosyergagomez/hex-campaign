"""Compact territories and the rotations used to distribute fortresses."""

import heapq
import math

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.terrain import HOME_RADIUS


def home_radius(map_size: int) -> int:
    if map_size in HOME_RADIUS:
        return HOME_RADIUS[map_size]
    return core_radius(initial_area(map_size))


def initial_area(map_size: int) -> int:
    return max(7, (map_size * 7 + 50) // 100)


def core_radius(area: int) -> int:
    return (math.isqrt(12 * area - 3) - 3) // 6


def checked_home_size(value: object, map_size: int) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 7 <= value < map_size // 2:
        raise DomainError("rules_invalid")
    return value


def rotate60(cell: Hex) -> Hex:
    """One sixth of a turn, clockwise, around the center of the disk."""
    return Hex(cell.q + cell.r, -cell.q)


def rotate(cell: Hex, sixths: int) -> Hex:
    turned = cell
    for _ in range(sixths % 6):
        turned = rotate60(turned)
    return turned


def owned(fort: Hex, radius: int, board: set[Hex], *, count: int | None = None) -> set[Hex]:
    if count is not None:
        return set(heapq.nsmallest(count, board, key=lambda cell: (
            distance(cell, fort), distance(cell, Hex(0, 0)), cell,
        )))
    return {cell for cell in board if distance(cell, fort) <= radius}
