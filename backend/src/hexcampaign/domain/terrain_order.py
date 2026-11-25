"""An order on a terrain map may cost more than one point per hex."""

from hexcampaign.domain.clock_march import Walker, walk
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Army, Game, living
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.sight import sees_army
from hexcampaign.domain.terrain import passable


def check_terrain_order(game: Game, player_id: str, paths: dict[str, tuple[Hex, ...]]) -> None:
    own = [army for army in living(game, player_id)]
    if {army.id for army in own} != set(paths):
        raise DomainError("order_illegal")
    board = set(game.hexes)
    plots = game.plots or {}
    _reject_illegal_steps(game, player_id, own, paths, board, plots)
    _reject_allies_in_the_way(game, own, paths, board, plots)


def _reject_illegal_steps(game, player_id, own, paths, board, plots) -> None:
    blocked = {Hex(army.q, army.r) for army in game.armies if sees_army(game, player_id, army)}
    blocked.difference_update(army.at() for army in own if army.at() is not None)
    for army in own:
        path = paths[army.id]
        if len(path) > len(board):
            raise DomainError("order_illegal")
        previous = army.at()
        assert previous is not None
        for index, step in enumerate(path):
            plot = plots.get(step)
            known = step in game.discovered.get(player_id, set())
            if step not in board or distance(previous, step) != 1 or plot is None:
                raise DomainError("order_illegal")
            if known and not passable(plot):
                raise DomainError("order_illegal")
            if step in blocked and index != len(path) - 1:
                raise DomainError("order_illegal")
            previous = step


def _reject_allies_in_the_way(game, own, paths, board, plots) -> None:
    moved = walk([_walker(game, army, paths[army.id]) for army in own], plots, board)
    for army in own:
        solo = walk([_walker(game, army, paths[army.id])], plots, board)
        if moved.positions[army.id] != solo.positions[army.id]:
            raise DomainError("order_illegal")
    occupied: set[Hex] = set()
    for cell in moved.positions.values():
        if cell in occupied:
            raise DomainError("order_illegal")
        occupied.add(cell)


def _walker(game: Game, army: Army, path: tuple[Hex, ...]) -> Walker:
    spot = army.at()
    assert spot is not None
    return Walker(army.id, army.player_id, spot, list(path), game.rules.movement, army.paid)
