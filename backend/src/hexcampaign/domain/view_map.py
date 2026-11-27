"""Hexes, tokens and fortresses one player is allowed to see."""

from hexcampaign.domain.game import Army, Fortress, Game, living
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.sight import gazed_cells, in_home, known_hex, sees_army
from hexcampaign.domain.territory import homes_by_player
from hexcampaign.domain.units import unit_gaze


def _owners_for(
    game: Game,
    cells: list[Hex],
    board: set[Hex],
    *,
    homes: dict[str, set[Hex]] | None = None,
) -> dict[Hex, str]:
    if not cells or game.plots is None:
        return {}
    wanted = set(cells)
    owners: dict[Hex, str] = {}
    claimed = homes if homes is not None else homes_by_player(game, board=board)
    for player_id, home in claimed.items():
        for cell in wanted & home:
            owners[cell] = player_id
        if len(owners) == len(wanted):
            break
    return owners

def _territorial_owners(
    game: Game,
    board: set[Hex] | None = None,
    *,
    homes: dict[str, set[Hex]] | None = None,
) -> dict[Hex, str]:
    if game.plots is None:
        owners: dict[Hex, str] = {}
        for cell in game.hexes:
            nearest = sorted(
                (distance(cell, fort.at()), fort.player_id) for fort in game.fortresses
            )
            if nearest and (len(nearest) == 1 or nearest[0][0] < nearest[1][0]):
                owners[cell] = nearest[0][1]
        return owners
    cells = set(game.hexes) if board is None else board
    claimed = homes if homes is not None else homes_by_player(game, board=cells)
    return {
        cell: player_id
        for player_id, home in claimed.items()
        for cell in home
    }


def _hex_view(
    game: Game,
    viewer: str,
    cell: Hex,
    owner: str | None,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> dict[str, object]:
    known = known_hex(game, viewer, cell, home=home, board=board)
    shown: dict[str, object] = {"q": cell.q, "r": cell.r, "known": known}
    plot = None if game.plots is None else game.plots.get(cell)
    if known:
        shown["ground"] = plot.ground if plot is not None else "llanura"
        shown["road"] = plot.road if plot is not None else False
        shown["bridge"] = plot.bridge if plot is not None else False
        shown["owner_id"] = owner
        shown["sight"] = _looking(game, viewer, cell, home=home, board=board)
    return shown


def _token_spot(game: Game, army: Army) -> tuple[int | None, int | None]:
    """Hide pieces until that seat is preparing its armies. The coordinates stay on the game."""
    if (
        game.plots is not None
        and game.phase in {"placing", "preparing"}
        and not game.naming
        and army.player_id not in game.road_ready
        and army.player_id not in game.prep_done
    ):
        return None, None
    return army.q, army.r


def _armies(
    game: Game,
    viewer: str,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> list[dict[str, object]]:
    shown: list[dict[str, object]] = []
    for army in game.armies:
        if not sees_army(game, viewer, army, home=home, board=board):
            continue
        q, r = _token_spot(game, army)
        if army.player_id != viewer and game.rules.visibility == "anonymous":
            shown.append(
                {
                    "id": army.id,
                    "q": q,
                    "r": r,
                    "kind": army.kind,
                    "anonymous": True,
                }
            )
            continue
        owned = army.player_id == viewer
        shown.append(
            {
                "id": army.id,
                "player_id": army.player_id,
                "name": army.name if owned else "",
                "commander": army.commander if owned else "",
                "race": army.race if owned else "",
                "roster": army.roster if owned else "",
                "q": q,
                "r": r,
                "destroyed": army.destroyed,
                "kind": army.kind,
                "anonymous": False,
                "paid": army.paid if owned else 0,
            }
        )
    return shown


def _fortresses(
    game: Game,
    viewer: str,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> list[dict[str, object]]:
    shown: list[dict[str, object]] = []
    live: set[Hex] = set()
    for fort in game.fortresses:
        cell = Hex(fort.q, fort.r)
        live.add(cell)
        if fort.player_id != viewer and not known_hex(game, viewer, cell, home=home, board=board):
            continue
        visible = _hold_visible(game, viewer, fort, home=home, board=board)
        shown.append(
            {
                "player_id": fort.player_id,
                "q": fort.q,
                "r": fort.r,
                "holder_id": fort.holder_id if visible else None,
                "hold": fort.hold if visible else 0,
            }
        )
    shown.extend(_remembered_fortresses(game, viewer, live, home=home, board=board))
    return shown


def _remembered_fortresses(
    game: Game,
    viewer: str,
    live: set[Hex],
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> list[dict[str, object]]:
    if game.plots is None:
        return []
    remembered: list[dict[str, object]] = []
    for key, owner in game.fort_memory.get(viewer, {}).items():
        if not owner:
            continue
        q_text, r_text = key.split(",")
        cell = Hex(int(q_text), int(r_text))
        if (
            cell in live
            or _looking(game, viewer, cell, home=home, board=board)
            or not known_hex(game, viewer, cell, home=home, board=board)
        ):
            continue
        remembered.append(
            {"player_id": owner, "q": cell.q, "r": cell.r, "holder_id": None, "hold": 0}
        )
    return remembered

def _hold_visible(
    game: Game,
    viewer: str,
    fort: Fortress,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> bool:
    if game.plots is not None and not _looking(game, viewer, fort.at(), home=home, board=board):
        return False
    if not fort.holder_id or fort.holder_id == viewer or game.rules.visibility in {"full", "total"}:
        return bool(fort.holder_id)
    if game.rules.visibility == "anonymous":
        return False
    cell = fort.at()
    return any(
        sees_army(game, viewer, army, home=home, board=board)
        and army.player_id == fort.holder_id
        and army.at() == cell
        for army in game.armies
    )

def _looking(
    game: Game,
    viewer: str,
    cell: Hex,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> bool:
    if game.rules.visibility in {"full", "total"}:
        return True
    if in_home(game, viewer, cell, home=home, board=board):
        return True
    for army in living(game, viewer):
        spot = army.at()
        if spot is None:
            continue
        reach = unit_gaze(army, None if game.plots is None else game.plots.get(spot))
        if cell in gazed_cells(game, spot, reach=reach):
            return True
    return False
