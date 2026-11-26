"""Home disks claimed by each fortress."""

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.land import home_radius, owned


def fortress_of(game: Game, player_id: str) -> Hex | None:
    fort = next((item for item in game.fortresses if item.player_id == player_id), None)
    return None if fort is None else fort.at()


def home_land(
    game: Game,
    player_id: str,
    *,
    board: set[Hex] | None = None,
) -> set[Hex]:
    fort = fortress_of(game, player_id)
    return set() if fort is None else disk_at(game, fort, board=board)


def require_home(
    game: Game,
    player_id: str,
    *,
    board: set[Hex] | None = None,
) -> tuple[set[Hex], Hex]:
    fort = fortress_of(game, player_id)
    if fort is None:
        raise DomainError("phase_invalid")
    return disk_at(game, fort, board=board), fort


def assigned_homes(game: Game, *, board: set[Hex] | None = None) -> dict[str, set[Hex]]:
    """The disk each seat was given before anyone moved a fortress."""
    cells = set(game.hexes) if board is None else board
    players = [member.player_id for member in game.members if member.status != "expelled"]
    if len(game.anchors) == len(players) and players:
        radius = home_radius(game.rules.map_size)
        return {
            player_id: owned(game.anchors[index], radius, cells, count=game.home_size)
            for index, player_id in enumerate(players)
        }
    return {
        player_id: {cell for cell in zone if cell in cells}
        for player_id, zone in game.discovered.items()
    }


def homes_by_player(game: Game, *, board: set[Hex] | None = None) -> dict[str, set[Hex]]:
    cells = set(game.hexes) if board is None else board
    return {
        fort.player_id: disk_at(game, fort.at(), board=cells)
        for fort in game.fortresses
    }


def disk_at(game: Game, fort: Hex, *, board: set[Hex] | None = None) -> set[Hex]:
    cells = set(game.hexes) if board is None else board
    return owned(
        fort,
        home_radius(game.rules.map_size),
        cells,
        count=game.home_size,
    )
