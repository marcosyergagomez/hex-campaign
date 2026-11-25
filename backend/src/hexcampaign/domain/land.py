"""The disk a fortress owns, and the turns that make a generated map symmetric."""

from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.terrain import HOME_RADIUS


def home_radius(map_size: int) -> int:
    return HOME_RADIUS[map_size]


def rotate60(cell: Hex) -> Hex:
    """One sixth of a turn, clockwise, around the center of the disk."""
    return Hex(cell.q + cell.r, -cell.q)


def rotate(cell: Hex, sixths: int) -> Hex:
    turned = cell
    for _ in range(sixths % 6):
        turned = rotate60(turned)
    return turned


def owned(fort: Hex, radius: int, board: set[Hex]) -> set[Hex]:
    return {cell for cell in board if distance(cell, fort) <= radius}
