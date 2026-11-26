"""A saved map is a picture of the ground. The campaign keeps its own copy."""

import random
from dataclasses import dataclass, replace
from functools import cache

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game
from hexcampaign.domain.hexes import DISK_RADIUS, TABLE_RADII, Hex, disk, distance, neighbors
from hexcampaign.domain.land import core_radius, initial_area, owned, rotate
from hexcampaign.domain.landscape import paint
from hexcampaign.domain.terrain import Plot, passable

# Geometric floor; landscape validation also checks five turns with local road refunds.
_SEPARATION = 15


@dataclass(frozen=True)
class Template:
    size: int
    seats: int | None
    generated: bool
    cells: dict[Hex, Plot]
    anchors: tuple[Hex, ...]
    home_size: int | None = None


def table_presets() -> list[dict[str, object]]:
    if len(TABLE_RADII) != 3 or tuple(sorted(set(TABLE_RADII))) != TABLE_RADII:
        raise DomainError("rules_invalid")
    result: list[dict[str, object]] = []
    scales = zip(("small", "medium", "large"), TABLE_RADII, strict=True)
    for index, (key, radius) in enumerate(scales):
        size = 1 + 3 * radius * (radius + 1)
        seats = []
        for count in (2, 3, 4):
            try:
                fortress_sites(size, count)
            except DomainError:
                continue
            seats.append(count)
        if not seats:
            raise DomainError("rules_invalid")
        result.append({
            "key": key, "size": size, "seats": seats,
            "recommend": min(seats, key=lambda count: abs(count - index - 2)),
            "home_size": initial_area(size),
        })
    return result


def generate(size: int, seats: int, rng: random.Random) -> Template:
    """One landscape. The seed moves the lake, the river and the ridge."""
    board = set(disk(size))
    turn = rng.randrange(6)
    sites = tuple(rotate(site, turn) for site in fortress_sites(size, seats))
    plots = paint(board, sites, rng)
    area = initial_area(size)
    _check_shape(plots, board, sites, area)
    return Template(size, seats, True, plots, sites, area)


@cache
def fortress_sites(size: int, seats: int) -> tuple[Hex, ...]:
    if size not in DISK_RADIUS or seats not in {2, 3, 4}:
        raise DomainError("rules_invalid")
    area = initial_area(size)
    radius = DISK_RADIUS[size]
    for ring in range(max(1, radius - core_radius(area)), radius):
        if seats == 2:
            sites = (Hex(ring, 0), Hex(-ring, 0))
        elif seats == 3:
            start = Hex(ring, 0)
            sites = (start, rotate(start, 2), rotate(start, 4))
        else:
            sites = _four(size, ring, area)
        if sites and min(distance(a, b) for a in sites for b in sites if a != b) >= _SEPARATION:
            return sites
    raise DomainError("rules_invalid")


def lay(game: Game, template: Template, surveyor: str | None) -> None:
    if template.size != game.rules.map_size or set(template.cells) != set(game.hexes):
        raise DomainError("rules_invalid")
    if game.rules.visibility not in {"total", "charted", "home"}:
        raise DomainError("rules_invalid")
    if template.generated and template.seats != game.rules.seats:
        raise DomainError("rules_invalid")
    game.plots = dict(template.cells)
    game.anchors = list(template.anchors)
    game.surveyor = surveyor
    game.home_size = template.home_size
    if template.generated:
        game.rules = replace(game.rules, placement="app")


def _check_shape(
    plots: dict[Hex, Plot],
    board: set[Hex],
    sites: tuple[Hex, ...],
    area: int,
) -> None:
    apart = min(distance(left, right) for left in sites for right in sites if left != right)
    if apart < _SEPARATION or len({distance(site, Hex(0, 0)) for site in sites}) != 1:
        raise DomainError("rules_invalid")
    claimed: set[Hex] = set()
    for fort in sites:
        if not passable(plots[fort]):
            raise DomainError("rules_invalid")
        home = owned(fort, 0, board, count=area)
        if claimed & home or len(home) != area:
            raise DomainError("rules_invalid")
        claimed.update(home)
        for cell in neighbors(fort):
            if cell in board and not passable(plots[cell]):
                raise DomainError("rules_invalid")
    if len(claimed) >= len(board) or Hex(0, 0) in claimed:
        raise DomainError("rules_invalid")


def _four(size: int, ring: int, area: int) -> tuple[Hex, ...]:
    board = set(disk(size))
    circle = [cell for cell in board if distance(cell, Hex(0, 0)) == ring]
    circle.sort()
    homes = {cell: owned(cell, 0, board, count=area) for cell in circle}
    best: tuple[int, tuple[Hex, ...]] | None = None
    for start in circle:
        opposite = rotate(start, 3)
        for other in circle:
            pair = rotate(other, 3)
            sites = (start, opposite, other, pair)
            if len(set(sites)) < 4 or any(site not in board for site in sites):
                continue
            apart = min(distance(left, right) for left in sites for right in sites if left != right)
            if apart < _SEPARATION:
                continue
            if any(homes[a] & homes[b] for a in sites for b in sites if a != b):
                continue
            ordered = tuple(sorted(set(sites)))
            if best is None or apart > best[0]:
                best = (apart, ordered)
    return () if best is None else best[1]
