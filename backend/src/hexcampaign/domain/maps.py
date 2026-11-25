"""A saved map is a picture of the ground. The campaign keeps its own copy."""

import random
from dataclasses import dataclass, replace

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game
from hexcampaign.domain.hexes import DISK_RADIUS, Hex, disk, distance, neighbors
from hexcampaign.domain.land import home_radius, owned, rotate
from hexcampaign.domain.rules import MAP_SIZES
from hexcampaign.domain.terrain import Plot

_SIZE_OF_RADIUS = {radius: size for size, radius in DISK_RADIUS.items()}
_ACCENTS = ("bosque", "colina", "tundra")


@dataclass(frozen=True)
class Template:
    size: int
    seats: int | None
    generated: bool
    cells: dict[Hex, Plot]
    anchors: tuple[Hex, ...]


def generate(size: int, seats: int, rng: random.Random) -> Template:
    """Symmetric plains, with the same accent in every home disk.

    Rivers, cliffs and roads belong on a map the player draws. They are not invented here.
    """
    if size not in MAP_SIZES or seats not in {2, 3, 4}:
        raise DomainError("rules_invalid")
    accent = rng.choice(_ACCENTS)
    board = set(disk(size))
    plots = {cell: Plot("llanura") for cell in board}
    sites = fortress_sites(size, seats)
    radius = home_radius(size)
    for fort in sites:
        _stamp(plots, fort, radius, board, accent)
    claimed: set[Hex] = set()
    for fort in sites:
        claimed.update(owned(fort, radius, board))
    if len(claimed) >= len(board):
        raise DomainError("rules_invalid")
    return Template(size, seats, True, plots, sites)


def fortress_sites(size: int, seats: int) -> tuple[Hex, ...]:
    radius = DISK_RADIUS[size]
    gap = 2 * home_radius(size) + 1
    if seats == 2:
        return (Hex(radius, 0), Hex(-radius, 0))
    if seats == 3:
        start = Hex(radius, 0)
        return (start, rotate(start, 2), rotate(start, 4))
    if seats == 4:
        return _four(radius, gap, home_radius(size))
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
    if template.generated:
        game.rules = replace(game.rules, placement="app")


def _stamp(plots: dict[Hex, Plot], fort: Hex, radius: int, board: set[Hex], accent: str) -> None:
    home = owned(fort, radius, board)
    step = _inward(fort)
    if step in home:
        plots[step] = Plot(accent)
    if radius < 2:
        return
    further = _inward(step)
    if further in home and further != fort:
        plots[further] = Plot("bosque" if accent == "colina" else "colina")


def _inward(cell: Hex) -> Hex:
    closer = distance(cell, Hex(0, 0))
    options = [item for item in neighbors(cell) if distance(item, Hex(0, 0)) < closer]
    options.sort()
    return options[0]


def _four(map_radius: int, gap: int, home: int) -> tuple[Hex, ...]:
    board = set(disk(_SIZE_OF_RADIUS[map_radius]))
    ring = [cell for cell in board if distance(cell, Hex(0, 0)) == map_radius]
    ring.sort()
    for start in ring:
        opposite = rotate(start, 3)
        for other in ring:
            pair = rotate(other, 3)
            sites = (start, opposite, other, pair)
            if len(set(sites)) < 4 or any(site not in board for site in sites):
                continue
            apart = min(distance(left, right) for left in sites for right in sites if left != right)
            if apart < gap:
                continue
            widths = {len(owned(site, home, board)) for site in sites}
            if len(widths) == 1:
                return tuple(sorted(set(sites)))
    raise DomainError("rules_invalid")
