"""The browser receives one player's view. Secret orders of the others are omitted."""

from datetime import datetime

from hexcampaign.domain.clock import overdue
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game, find_member, living
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.roads import road_progress
from hexcampaign.domain.sight import gazed_cells, in_home, known_hex, sees_army
from hexcampaign.domain.territory import homes_by_player


def project(game: Game, viewer: str, now: datetime) -> dict[str, object]:
    member = find_member(game, viewer)
    staff = member is not None and member.role in {"owner", "admin"} and member.status == "active"
    board = set(game.hexes)
    homes = homes_by_player(game, board=board) if game.plots is not None else None
    home = homes.get(viewer, set()) if homes is not None else set()
    owners = _territorial_owners(game, board, homes=homes)
    body = {
        "revision": game.revision,
        "name": game.name,
        "description": game.description,
        "phase": game.phase,
        "turn": game.turn,
        "rules": {
            "seats": game.rules.seats,
            "armies": game.rules.armies,
            "movement": game.rules.movement,
            "map_size": game.rules.map_size,
            "visibility": game.rules.visibility,
            "victory": game.rules.victory,
            "hold_turns": game.rules.hold_turns,
            "placement": game.rules.placement,
            "order_days": game.rules.order_days,
            "battle_days": game.rules.battle_days,
            "missed_turns": game.rules.missed_turns,
        },
        "you": None if member is None else _you(member, game),
        "members": [
            _member_view(item, game, staff or item.player_id == viewer) for item in game.members
        ],
        # The atlas stays sealed until kickoff; nobody peeks during recruiting.
        "hexes": []
        if game.phase == "recruiting"
        else [
            _hex_view(game, viewer, cell, owners.get(cell), home=home, board=board)
            for cell in game.hexes
        ],
        "armies": []
        if game.phase == "recruiting"
        else _armies(game, viewer, home=home, board=board),
        "fortresses": []
        if game.phase == "recruiting"
        else _fortresses(game, viewer, home=home, board=board),
        "orders": {
            army_id: [{"q": cell.q, "r": cell.r} for cell in path]
            for army_id, path in game.orders.get(viewer, {}).items()
        },
        "battles": [
            _battle_view(game, battle, viewer, staff, now)
            for battle in game.battles
            if _show_battle(game, battle, viewer, staff, home=home, board=board)
        ],
        "notices": list(game.notices) if staff else [],
        "events": list(game.events),
        "chronicle": _chronicle(game, member is not None),
        "winners": list(game.winners),
        "orders_due": game.phase == "orders"
        and overdue(game.orders_opened_at, game.rules.order_days, now),
        "road_ready": sorted(game.road_ready),
        "lobby_ready": sorted(game.lobby_ready) if game.phase == "recruiting" else [],
        "roads": _roads_view(game, viewer),
    }
    return body


def project_roads_delta(
    game: Game,
    viewer: str,
    changed: list[Hex],
) -> dict[str, object]:
    """Slim preparing-phase patch: road counters plus only the hexes that moved."""
    board = set(game.hexes)
    homes = homes_by_player(game, board=board) if game.plots is not None else None
    home = homes.get(viewer, set()) if homes is not None else set()
    owners = _owners_for(game, changed, board, homes=homes)
    return {
        "kind": "roads_delta",
        "revision": game.revision,
        "phase": game.phase,
        "turn": game.turn,
        "road_ready": sorted(game.road_ready),
        "roads": _roads_view(game, viewer),
        "hexes": [
            _hex_view(game, viewer, cell, owners.get(cell), home=home, board=board)
            for cell in changed
            if cell in board
        ],
    }


def _roads_view(game: Game, viewer: str) -> dict[str, object] | None:
    if game.phase != "preparing" or game.plots is None or find_member(game, viewer) is None:
        return None
    try:
        budget, laid = road_progress(game, viewer)
    except DomainError:
        return None
    return {
        "budget": budget,
        "laid": laid,
        "left": max(0, budget - laid),
        "ready": viewer in game.road_ready,
    }


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


def _you(member, game: Game) -> dict[str, object]:
    return {
        "player_id": member.player_id,
        "alias": member.alias,
        "role": member.role,
        "status": member.status,
        "missed": member.missed,
        "faction": member.faction,
        "color": member.color,
        "ready": member.player_id in game.lobby_ready,
    }


def _member_view(member, game: Game, show_missed: bool) -> dict[str, object]:
    shown = {
        "player_id": member.player_id,
        "alias": member.alias,
        "role": member.role,
        "status": member.status,
        "faction": member.faction,
        "color": member.color,
        "ready": member.player_id in game.lobby_ready,
    }
    if show_missed:
        shown["missed"] = member.missed
    return shown


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
    return shown


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
        if army.player_id != viewer and game.rules.visibility == "anonymous":
            shown.append({"id": army.id, "q": army.q, "r": army.r, "anonymous": True})
            continue
        shown.append(
            {
                "id": army.id,
                "player_id": army.player_id,
                "name": army.name,
                "commander": army.commander,
                "race": army.race,
                "roster": army.roster,
                "q": army.q,
                "r": army.r,
                "destroyed": army.destroyed,
                "anonymous": False,
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


def _show_battle(
    game: Game,
    battle,
    viewer: str,
    staff: bool,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> bool:
    if game.plots is not None:
        return _show_terrain_battle(game, battle, viewer, staff, home=home, board=board)
    if staff or viewer in battle.players or game.rules.visibility == "full":
        return True
    # An anonymous token has no name. A battle list would put the name back.
    if game.rules.visibility == "anonymous":
        return False
    cell = Hex(battle.q, battle.r)
    if not known_hex(game, viewer, cell, home=home, board=board):
        return False
    involved = [army for army in game.armies if army.id in set(battle.army_ids)]
    if any(sees_army(game, viewer, army, home=home, board=board) for army in involved):
        return True
    spots = [army.at() for army in living(game, viewer)]
    return any(spot is not None and distance(cell, spot) <= 1 for spot in spots)


def _hold_visible(
    game: Game,
    viewer: str,
    fort,
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


def _battle_view(game: Game, battle, viewer: str, staff: bool, now: datetime) -> dict[str, object]:
    conflict = len(battle.reports) >= 2 and len(set(battle.reports.values())) > 1
    shown: dict[str, object] = {
        "id": battle.id,
        "turn": battle.turn,
        "q": battle.q,
        "r": battle.r,
        "army_ids": list(battle.army_ids),
        "players": list(battle.players),
        "result": battle.result,
        "reverted": battle.reverted,
        "due": overdue(battle.opened_at, game.rules.battle_days, now),
        "conflict": conflict,
        "yours": battle.reports.get(viewer),
    }
    if staff:
        shown["reports"] = dict(battle.reports)
    return shown


def _show_terrain_battle(
    game: Game,
    battle,
    viewer: str,
    staff: bool,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> bool:
    if viewer in battle.players or game.rules.visibility in {"full", "total"}:
        return True
    if staff and battle.result is None:
        return True
    cell = Hex(battle.q, battle.r)
    if not known_hex(game, viewer, cell, home=home, board=board):
        return False
    involved = [army for army in game.armies if army.id in set(battle.army_ids)]
    return any(
        sees_army(game, viewer, army, home=home, board=board) for army in involved
    ) or _looking(game, viewer, cell, home=home, board=board)


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
        if spot is not None and cell in gazed_cells(game, spot):
            return True
    return False


def _chronicle(game: Game, member: bool) -> list[dict[str, object]]:
    """The story stays in the document during the war and leaves it only at the end."""
    if game.phase != "finished" or not member:
        return []
    return [dict(item) for item in game.chronicle]
