"""Player-laid roads in the preparation phase, before the first turn."""

from dataclasses import replace
from datetime import datetime

from hexcampaign.domain.chronicle import remember
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game, bump, require_phase, require_player
from hexcampaign.domain.hexes import Hex, distance, neighbors
from hexcampaign.domain.terrain import Plot, passable
from hexcampaign.domain.territory import require_home


def road_budget(game: Game, player_id: str) -> int:
    """Two routes from the keep to the home rim: one piece per ring, twice."""
    home, fort = require_home(game, player_id)
    return _budget(home, fort)


def roads_laid(game: Game, player_id: str) -> set[Hex]:
    home, fort = require_home(game, player_id)
    if game.plots is None:
        return set()
    return _laid(home, fort, game.plots)


def road_progress(game: Game, player_id: str) -> tuple[int, int]:
    """Budget and pieces already laid, computed from one home lookup."""
    home, fort = require_home(game, player_id)
    if game.plots is None:
        return _budget(home, fort), 0
    return _budget(home, fort), len(_laid(home, fort, game.plots))


def place_road(game: Game, actor: str, cell: Hex) -> Game:
    home, fort, plots = _editing(game, actor)
    if cell not in plots or cell not in home or cell == fort or not passable(plots[cell]):
        raise DomainError("order_illegal")
    laid = _laid(home, fort, plots)
    if cell in laid:
        return game
    if len(laid) >= _budget(home, fort) or not _touches_network(cell, fort, laid):
        raise DomainError("order_illegal")
    plot = plots[cell]
    plots[cell] = replace(plot, road=True, bridge=plot.bridge or plot.ground == "rio")
    return bump(game)


def clear_road(game: Game, actor: str, cell: Hex) -> Game:
    home, fort, plots = _editing(game, actor)
    if cell not in plots or cell not in home or not plots[cell].road:
        raise DomainError("order_illegal")
    remaining = _laid(home, fort, plots) - {cell}
    if remaining and not _connected_to_fort(remaining, fort):
        raise DomainError("order_illegal")
    plot = plots[cell]
    plots[cell] = Plot(plot.ground, road=False, bridge=False)
    return bump(game)


def finish_roads(game: Game, actor: str, now: datetime) -> Game:
    """This seat leaves the roads and goes on to its armies. The others are not waited on."""
    del now
    require_phase(game, "preparing")
    member = require_player(game, actor)
    if member.status != "active":
        raise DomainError("forbidden")
    if not _fort_locked(game, actor) or game.naming or actor in game.prep_done:
        raise DomainError("phase_invalid")
    if actor in game.road_ready:
        return game
    game.road_ready.add(actor)
    remember(game, "roads_ready", player_id=actor)
    for army in game.armies:
        if army.player_id == actor and not army.destroyed:
            army.q = None
            army.r = None
    return bump(game)


def _fort_locked(game: Game, actor: str) -> bool:
    """A seat may lay roads once its own fortress is fixed, even if others are still placing."""
    if game.plots is None or not game.fort_open:
        return True
    return actor in game.lobby_ready


def _editing(game: Game, actor: str) -> tuple[set[Hex], Hex, dict[Hex, Plot]]:
    require_phase(game, "preparing")
    require_player(game, actor)
    if not _fort_locked(game, actor) or game.naming or actor in game.road_ready or actor in game.prep_done:
        raise DomainError("phase_invalid")
    if game.plots is None:
        raise DomainError("order_illegal")
    home, fort = require_home(game, actor)
    return home, fort, game.plots


def _budget(home: set[Hex], fort: Hex) -> int:
    return 2 * max((distance(cell, fort) for cell in home), default=0)


def _laid(home: set[Hex], fort: Hex, plots: dict[Hex, Plot]) -> set[Hex]:
    return {cell for cell in home if cell != fort and plots[cell].road}


def _touches_network(cell: Hex, fort: Hex, laid: set[Hex]) -> bool:
    return any(other == fort or other in laid for other in neighbors(cell))


def _connected_to_fort(roads: set[Hex], fort: Hex) -> bool:
    seen = {fort}
    stack = [fort]
    while stack:
        cell = stack.pop()
        for other in neighbors(cell):
            if other in roads and other not in seen:
                seen.add(other)
                stack.append(other)
    return roads <= seen
