"""The browser receives one player's view. Secret orders of the others are omitted."""

from datetime import datetime

from hexcampaign.domain.clock import overdue
from hexcampaign.domain.game import Game, find_member, living
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.sight import known_hex, sees_army


def project(game: Game, viewer: str, now: datetime) -> dict[str, object]:
    member = find_member(game, viewer)
    staff = member is not None and member.role in {"owner", "admin"} and member.status == "active"
    body = {
        "revision": game.revision,
        "name": game.name,
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
        "you": None if member is None else _you(member),
        "members": [_member_view(item, staff or item.player_id == viewer) for item in game.members],
        "hexes": [
            {"q": cell.q, "r": cell.r, "known": known_hex(game, viewer, cell)}
            for cell in game.hexes
        ],
        "armies": _armies(game, viewer),
        "fortresses": _fortresses(game, viewer),
        "orders": {
            army_id: [{"q": cell.q, "r": cell.r} for cell in path]
            for army_id, path in game.orders.get(viewer, {}).items()
        },
        "battles": [
            _battle_view(game, battle, viewer, staff, now)
            for battle in game.battles
            if _show_battle(game, battle, viewer, staff)
        ],
        "notices": list(game.notices) if staff else [],
        "events": list(game.events),
        "chronicle": _chronicle(game, member is not None),
        "winners": list(game.winners),
        "orders_due": game.phase == "orders"
        and overdue(game.orders_opened_at, game.rules.order_days, now),
    }
    return body


def _you(member) -> dict[str, object]:
    return {
        "player_id": member.player_id,
        "alias": member.alias,
        "role": member.role,
        "status": member.status,
        "missed": member.missed,
    }


def _member_view(member, show_missed: bool) -> dict[str, object]:
    shown = {
        "player_id": member.player_id,
        "alias": member.alias,
        "role": member.role,
        "status": member.status,
    }
    if show_missed:
        shown["missed"] = member.missed
    return shown


def _armies(game: Game, viewer: str) -> list[dict[str, object]]:
    shown: list[dict[str, object]] = []
    for army in game.armies:
        if not sees_army(game, viewer, army):
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


def _fortresses(game: Game, viewer: str) -> list[dict[str, object]]:
    shown: list[dict[str, object]] = []
    for fort in game.fortresses:
        cell = Hex(fort.q, fort.r)
        if fort.player_id != viewer and not known_hex(game, viewer, cell):
            continue
        visible = _hold_visible(game, viewer, fort)
        shown.append(
            {
                "player_id": fort.player_id,
                "q": fort.q,
                "r": fort.r,
                "holder_id": fort.holder_id if visible else None,
                "hold": fort.hold if visible else 0,
            }
        )
    return shown


def _show_battle(game: Game, battle, viewer: str, staff: bool) -> bool:
    if staff or viewer in battle.players or game.rules.visibility == "full":
        return True
    # An anonymous token has no name. A battle list would put the name back.
    if game.rules.visibility == "anonymous":
        return False
    cell = Hex(battle.q, battle.r)
    if not known_hex(game, viewer, cell):
        return False
    involved = [army for army in game.armies if army.id in set(battle.army_ids)]
    if any(sees_army(game, viewer, army) for army in involved):
        return True
    spots = [army.at() for army in living(game, viewer)]
    return any(spot is not None and distance(cell, spot) <= 1 for spot in spots)


def _hold_visible(game: Game, viewer: str, fort) -> bool:
    if not fort.holder_id or fort.holder_id == viewer or game.rules.visibility == "full":
        return bool(fort.holder_id)
    if game.rules.visibility == "anonymous":
        return False
    cell = fort.at()
    return any(
        sees_army(game, viewer, army) and army.player_id == fort.holder_id and army.at() == cell
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


def _chronicle(game: Game, member: bool) -> list[dict[str, object]]:
    """The story stays in the document during the war and leaves it only at the end."""
    if game.phase != "finished" or not member:
        return []
    return [dict(item) for item in game.chronicle]
