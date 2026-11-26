"""Player-laid roads in the preparation phase, before the first turn."""

from dataclasses import replace
from datetime import datetime

from hexcampaign.domain.chronicle import remember
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game, bump, require_phase, require_player, seated
from hexcampaign.domain.hexes import Hex, distance, neighbors
from hexcampaign.domain.phases import open_first_turn
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
    """Mark the player done. When every seat is ready, the first turn opens."""
    require_phase(game, "preparing")
    member = require_player(game, actor)
    if member.status != "active":
        raise DomainError("forbidden")
    if actor in game.road_ready:
        return game
    game.road_ready.add(actor)
    remember(game, "roads_ready", player_id=actor)
    waiting = {item.player_id for item in seated(game) if item.status == "active"}
    if waiting <= game.road_ready:
        game.road_ready = set()
        open_first_turn(game, now)
        remember(game, "preparation_closed")
    return bump(game)


def _editing(game: Game, actor: str) -> tuple[set[Hex], Hex, dict[Hex, Plot]]:
    require_phase(game, "preparing")
    require_player(game, actor)
    if actor in game.road_ready:
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
