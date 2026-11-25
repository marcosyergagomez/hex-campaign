"""A player sees their own armies. Everyone else depends on the fog and the visibility rule."""

from hexcampaign.domain.game import Army, Game, living
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.land import home_radius, owned
from hexcampaign.domain.terrain import gaze_from


def sees_army(game: Game, viewer: str, army: Army) -> bool:
    if army.player_id == viewer:
        return True
    if army.destroyed or army.q is None or army.r is None:
        return False
    if game.rules.visibility in {"full", "total"}:
        return True
    cell = Hex(army.q, army.r)
    if game.plots is not None and game.rules.visibility not in {"total", "charted", "home"}:
        return cell in game.discovered.get(viewer, set()) and in_home(game, viewer, cell)
    if in_home(game, viewer, cell):
        return True
    if game.plots is None and cell not in game.discovered.get(viewer, set()):
        return False
    if game.plots is None and game.rules.visibility == "anonymous":
        return True
    if game.plots is None:
        return any(distance(cell, Hex(own.q, own.r)) <= 1 for own in living(game, viewer))
    if game.rules.visibility == "home" and cell not in game.discovered.get(viewer, set()):
        return False
    return any(_reaches(game, own, cell) for own in living(game, viewer))


def known_hex(game: Game, viewer: str, cell: Hex) -> bool:
    if game.rules.visibility in {"full", "total", "charted"}:
        return cell in set(game.hexes)
    if in_home(game, viewer, cell):
        return True
    return cell in game.discovered.get(viewer, set())


def in_home(game: Game, viewer: str, cell: Hex) -> bool:
    if game.plots is None:
        return False
    board = set(game.hexes)
    radius = home_radius(game.rules.map_size)
    for fort in game.fortresses:
        if fort.player_id == viewer and cell in owned(fort.at(), radius, board):
            return True
    return False


def gazed_cells(game: Game, origin: Hex) -> set[Hex]:
    reach = gaze_from(None if game.plots is None else game.plots.get(origin))
    return {cell for cell in game.hexes if distance(cell, origin) <= reach}


def _reaches(game: Game, army: Army, cell: Hex) -> bool:
    spot = army.at()
    if spot is None:
        return False
    reach = gaze_from(None if game.plots is None else game.plots.get(spot))
    return distance(cell, spot) <= reach


def remember_fort(game: Game, viewer: str, cell: Hex) -> None:
    owner = next((fort.player_id for fort in game.fortresses if fort.at() == cell), None)
    game.fort_memory.setdefault(viewer, {})[f"{cell.q},{cell.r}"] = owner


def remembered_fort(game: Game, viewer: str, cell: Hex) -> str | None:
    return game.fort_memory.get(viewer, {}).get(f"{cell.q},{cell.r}")
