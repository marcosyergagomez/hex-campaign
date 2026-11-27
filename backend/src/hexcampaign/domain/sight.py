"""A player sees their own armies. Everyone else depends on the fog and the visibility rule."""

from hexcampaign.domain.game import Army, Game, living
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.terrain import gaze_from
from hexcampaign.domain.territory import home_land
from hexcampaign.domain.units import unit_gaze


def equalize_fog(game: Game) -> bool:
    """Fog binds every seat. Drop the legacy surveyor atlas privilege."""
    if not game.surveyor:
        return False
    surveyor = game.surveyor
    game.surveyor = None
    if (
        game.plots is not None
        and game.rules.visibility == "home"
        and game.phase not in {"recruiting", "setup"}
    ):
        board = set(game.hexes)
        game.discovered[surveyor] = home_land(game, surveyor, board=board)
    return True


def sees_army(
    game: Game,
    viewer: str,
    army: Army,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> bool:
    if army.player_id == viewer:
        return True
    if army.destroyed or army.q is None or army.r is None:
        return False
    cell = Hex(army.q, army.r)
    if game.plots is None:
        return _sees_without_terrain(game, viewer, cell)
    return _sees_with_terrain(game, viewer, cell, home=home, board=board)


def _sees_without_terrain(game: Game, viewer: str, cell: Hex) -> bool:
    if game.rules.visibility == "full":
        return True
    if cell not in game.discovered.get(viewer, set()):
        return False
    if game.rules.visibility == "anonymous":
        return True
    return any(
        own.q is not None
        and own.r is not None
        and distance(cell, Hex(own.q, own.r)) <= 1
        for own in living(game, viewer)
    )


def _sees_with_terrain(
    game: Game,
    viewer: str,
    cell: Hex,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> bool:
    if game.rules.visibility in {"full", "total"}:
        return True
    if game.rules.visibility not in {"charted", "home"}:
        return False
    if in_home(game, viewer, cell, home=home, board=board):
        return True
    if game.rules.visibility == "home" and cell not in game.discovered.get(viewer, set()):
        return False
    return any(_reaches(game, own, cell) for own in living(game, viewer))


def known_hex(
    game: Game,
    viewer: str,
    cell: Hex,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> bool:
    cells = board if board is not None else set(game.hexes)
    if game.rules.visibility in {"full", "total", "charted"}:
        return cell in cells
    if in_home(game, viewer, cell, home=home, board=cells):
        return True
    return cell in game.discovered.get(viewer, set())


def in_home(
    game: Game,
    viewer: str,
    cell: Hex,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> bool:
    if game.plots is None:
        return False
    claimed = home if home is not None else home_land(game, viewer, board=board)
    return cell in claimed


def gazed_cells(game: Game, origin: Hex, *, reach: int | None = None) -> set[Hex]:
    if reach is None:
        reach = gaze_from(None if game.plots is None else game.plots.get(origin))
    return {cell for cell in game.hexes if distance(cell, origin) <= reach}


def _reaches(game: Game, army: Army, cell: Hex) -> bool:
    spot = army.at()
    if spot is None:
        return False
    reach = unit_gaze(army, None if game.plots is None else game.plots.get(spot))
    return distance(cell, spot) <= reach


def remember_fort(game: Game, viewer: str, cell: Hex) -> None:
    owner = next((fort.player_id for fort in game.fortresses if fort.at() == cell), None)
    game.fort_memory.setdefault(viewer, {})[f"{cell.q},{cell.r}"] = owner
