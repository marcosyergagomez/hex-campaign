"""The previous turn is the only snapshot.

Revert puts the board back. An expulsion that happened later stays.
"""

import copy

from hexcampaign.domain.game import Game, find_member
from hexcampaign.domain.hexes import Hex


def capture(game: Game) -> dict[str, object]:
    return {
        "phase": game.phase,
        "turn": game.turn,
        "orders_opened_at": game.orders_opened_at,
        "winners": list(game.winners),
        "armies": [
            {"id": army.id, "q": army.q, "r": army.r, "destroyed": army.destroyed}
            for army in game.armies
        ],
        "fortresses": [
            {"player_id": fort.player_id, "holder_id": fort.holder_id, "hold": fort.hold}
            for fort in game.fortresses
        ],
        "discovered": {
            player_id: [{"q": cell.q, "r": cell.r} for cell in sorted(cells)]
            for player_id, cells in game.discovered.items()
        },
        "orders": {
            player_id: {
                army_id: [{"q": cell.q, "r": cell.r} for cell in path]
                for army_id, path in orders.items()
            }
            for player_id, orders in game.orders.items()
        },
        "members": [
            {
                "player_id": member.player_id,
                "status": member.status,
                "missed": member.missed,
                "cause": member.cause,
            }
            for member in game.members
        ],
        "battle_ids": [battle.id for battle in game.battles],
        "previous": copy.deepcopy(game.previous),
    }


def restore(game: Game, board: dict) -> None:
    """Put positions, orders and turn-caused status back. An account closure stays inactive."""
    saved_armies = {item["id"]: item for item in board["armies"]}
    for army in game.armies:
        saved = saved_armies.get(army.id)
        owner = find_member(game, army.player_id)
        if saved is None or (owner is not None and owner.status == "expelled"):
            continue
        army.q = saved["q"]
        army.r = saved["r"]
        army.destroyed = saved["destroyed"]
    saved_forts = {item["player_id"]: item for item in board["fortresses"]}
    for fort in game.fortresses:
        saved = saved_forts.get(fort.player_id)
        if saved is None:
            continue
        fort.holder_id = saved["holder_id"]
        fort.hold = saved["hold"]
    game.discovered = {
        str(player_id): {Hex(item["q"], item["r"]) for item in cells}
        for player_id, cells in board["discovered"].items()
    }
    game.orders = {
        str(player_id): {
            str(army_id): tuple(Hex(item["q"], item["r"]) for item in path)
            for army_id, path in orders.items()
        }
        for player_id, orders in board["orders"].items()
    }
    game.phase = board["phase"]
    game.turn = board["turn"]
    game.orders_opened_at = board["orders_opened_at"]
    game.winners = list(board["winners"])
    saved_members = {item["player_id"]: item for item in board["members"]}
    for member in game.members:
        saved = saved_members.get(member.player_id)
        if saved is None or member.status == "expelled":
            continue
        member.missed = saved["missed"]
        if member.cause == "account":
            continue
        member.status = saved["status"]
        member.cause = saved["cause"]
    known = set(board["battle_ids"])
    for battle in game.battles:
        if battle.id not in known:
            battle.reverted = True
            battle.result = None
    game.events.append({"turn": board["turn"], "code": "reverted"})
    del game.events[:-30]
    game.previous = board["previous"]
