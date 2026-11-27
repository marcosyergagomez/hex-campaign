"""The browser receives one player's view. Secret orders of the others are omitted."""

from datetime import datetime

from hexcampaign.domain.clock import overdue
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game, Member, find_member
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.roads import road_progress
from hexcampaign.domain.territory import assigned_homes, disk_at, homes_by_player
from hexcampaign.domain.view_map import (
    _armies,
    _fortresses,
    _hex_view,
    _owners_for,
    _territorial_owners,
)
from hexcampaign.domain.view_playback import _battle_view, _playback, _show_battle


def project(game: Game, viewer: str, now: datetime) -> dict[str, object]:
    member = find_member(game, viewer)
    staff = member is not None and member.role in {"owner", "admin"} and member.status == "active"
    board = set(game.hexes)
    # Keep the starting disk fixed while the fortress can still be moved.
    homes: dict[str, set[Hex]] | None
    if game.plots is not None and (game.phase == "placing" or game.fort_open):
        homes = assigned_homes(game, board=board)
        for fort in game.fortresses:
            if fort.player_id in game.lobby_ready:
                homes[fort.player_id] = disk_at(game, fort.at(), board=board)
    else:
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
            "roster_required": game.rules.roster_required,
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
        "playback": _playback(game, viewer, home=home),
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
        "lobby_ready": sorted(game.lobby_ready)
        if game.phase in {"recruiting", "placing"} or game.fort_open
        else [],
        "naming": game.naming,
        "fort_open": game.fort_open,
        "prep_done": sorted(game.prep_done) if game.phase in {"placing", "preparing"} else [],
        "prep": preparation_stage(game, viewer),
        "roads": _roads_view(game, viewer),
    }
    return body


def project_fort_delta(game: Game, viewer: str) -> dict[str, object]:
    """The mover's own pieces. Other seats stay out of this shortcut."""
    return {
        "kind": "fort_delta",
        "revision": game.revision,
        "phase": game.phase,
        "fortresses": [
            {"player_id": fort.player_id, "q": fort.q, "r": fort.r}
            for fort in game.fortresses
            if fort.player_id == viewer
        ],
        "armies": [
            {"id": army.id, "q": army.q, "r": army.r}
            for army in game.armies
            if army.player_id == viewer and army.q is not None and army.r is not None
        ],
    }


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
        "naming": game.naming,
        "fort_open": game.fort_open,
        "prep_done": sorted(game.prep_done),
        "prep": preparation_stage(game, viewer),
        "roads": _roads_view(game, viewer),
        "hexes": [
            _hex_view(game, viewer, cell, owners.get(cell), home=home, board=board)
            for cell in changed
            if cell in board
        ],
    }


def preparation_stage(game: Game, viewer: str) -> str | None:
    """The step this seat is on. Others may be on a different step."""
    if game.phase not in {"placing", "preparing"} or game.plots is None:
        return None
    member = find_member(game, viewer)
    if member is None or member.status != "active":
        return None
    if (game.phase == "placing" or game.fort_open) and viewer not in game.lobby_ready:
        return "fort"
    if viewer in game.prep_done:
        return "waiting"
    if game.naming or viewer in game.road_ready:
        return "armies"
    return "roads"


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

def _you(member: Member, game: Game) -> dict[str, object]:
    return {
        "player_id": member.player_id,
        "alias": member.alias,
        "role": member.role,
        "status": member.status,
        "missed": member.missed,
        "faction": member.faction,
        "color": member.color,
        "ready": member.player_id in game.lobby_ready,
        "orders_locked": member.player_id in game.orders,
    }


def _member_view(member: Member, game: Game, show_missed: bool) -> dict[str, object]:
    shown = {
        "player_id": member.player_id,
        "alias": member.alias,
        "role": member.role,
        "status": member.status,
        "faction": member.faction,
        "color": member.color,
        "ready": member.player_id in game.lobby_ready,
        "orders_locked": member.player_id in game.orders,
    }
    if show_missed:
        shown["missed"] = member.missed
    return shown

def _chronicle(game: Game, member: bool) -> list[dict[str, object]]:
    """The story stays in the document during the war and leaves it only at the end."""
    if game.phase != "finished" or not member:
        return []
    return [dict(item) for item in game.chronicle]
