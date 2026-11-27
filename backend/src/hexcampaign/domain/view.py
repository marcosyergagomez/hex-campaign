"""The browser receives one player's view. Secret orders of the others are omitted."""

from datetime import datetime

from hexcampaign.domain.clock import overdue
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Army, Game, find_member, living
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.roads import road_progress
from hexcampaign.domain.sight import gazed_cells, in_home, known_hex, sees_army
from hexcampaign.domain.territory import assigned_homes, disk_at, homes_by_player
from hexcampaign.domain.units import unit_gaze


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


def _shown_march_turn(game: Game) -> int | None:
    """The turn whose march can be replayed. Orders for the open turn stay secret."""
    if game.phase == "orders":
        return game.turn - 1 if game.turn > 1 else None
    if game.phase in {"battles", "finished"} and game.turn > 0:
        return game.turn
    return None


def _playback(
    game: Game,
    viewer: str,
    *,
    home: set[Hex] | None,
) -> dict[str, object]:
    march_turn = _shown_march_turn(game)
    if march_turn is None:
        return {"turn": 0, "moves": []}
    events = [
        event
        for event in game.chronicle
        if event.get("code") == "marched" and event.get("turn") == march_turn
    ]
    sequences = {
        army_id: sequence
        for event in events
        if (army_id := event.get("army_id")) and isinstance(army_id, str)
        and (sequence := _march_sequence(event)) is not None
    }
    moves: list[dict[str, object]] = []
    for event in events:
        move = _visible_march(game, viewer, event, sequences, home=home)
        if move is not None:
            moves.append(move)
    return {"turn": march_turn, "moves": moves}


def _march_sequence(event: dict[str, object]) -> list[Hex] | None:
    origin = _event_hex(event.get("origin"))
    if origin is None:
        return None
    sequence = [origin]
    raw = event.get("trail")
    if isinstance(raw, list):
        for item in raw:
            cell = _event_hex(item)
            if cell is not None:
                sequence.append(cell)
    destination = _event_hex(event.get("destination"))
    if destination is not None and sequence[-1] != destination:
        sequence.append(destination)
    return sequence


def _visible_march(
    game: Game,
    viewer: str,
    event: dict[str, object],
    sequences: dict[str, list[Hex]],
    *,
    home: set[Hex] | None,
) -> dict[str, object] | None:
    army_id = event.get("army_id")
    if not isinstance(army_id, str) or not army_id:
        return None
    sequence = sequences.get(army_id)
    if sequence is None:
        return None
    own = event.get("player_id") == viewer
    lost = False
    offset = 0
    if not own:
        window = _watched_window(game, viewer, sequence, sequences, home=home)
        if window is None:
            return None
        sequence, lost, offset = window
    if len(sequence) < 2 and not lost:
        return None
    shown: dict[str, object] = {
        "army_id": army_id,
        "from": {"q": sequence[0].q, "r": sequence[0].r},
        "steps": [{"q": cell.q, "r": cell.r} for cell in sequence[1:]],
    }
    costs = _hop_costs(event.get("costs"), len(sequence) - 1, offset)
    if costs is not None:
        shown["costs"] = costs
    if not shown["steps"] and lost:
        shown["steps"] = [{"q": sequence[0].q, "r": sequence[0].r}]
    if lost:
        army = next((item for item in game.armies if item.id == army_id), None)
        member = None if army is None else find_member(game, army.player_id)
        shown["lost"] = True
        shown["kind"] = army.kind if army is not None else "army"
        anonymous = game.rules.visibility == "anonymous"
        shown["name"] = "" if army is None or anonymous else army.name
        shown["faction"] = "" if member is None or anonymous else member.faction
        shown["color"] = "" if member is None or anonymous else member.color
    return shown


def _hop_costs(raw: object, hops: int, offset: int) -> list[int] | None:
    """Points spent on each visible hop. Missing on marches saved before this field."""
    if hops <= 0 or not isinstance(raw, list):
        return None
    sliced = raw[offset:offset + hops]
    if len(sliced) != hops or any(type(item) is not int or item < 1 for item in sliced):
        return None
    return sliced


def _watched_window(
    game: Game,
    viewer: str,
    sequence: list[Hex],
    sequences: dict[str, list[Hex]],
    *,
    home: set[Hex] | None,
) -> tuple[list[Hex], bool, int] | None:
    """The part of an enemy march this player could see, and whether sight broke."""
    span = max((len(path) for path in sequences.values()), default=len(sequence))
    seen = [
        _seen_during(
            game,
            viewer,
            sequence[min(frame, len(sequence) - 1)],
            frame,
            sequences,
            home=home,
        )
        for frame in range(span)
    ]
    if not any(seen):
        return None
    if seen[-1]:
        end = len(seen) - 1
        start = end
        while start > 0 and seen[start - 1]:
            start -= 1
        start_index = min(start, len(sequence) - 1)
        return sequence[start_index:], False, start_index
    start = seen.index(True)
    end = start
    while end + 1 < len(seen) and seen[end + 1]:
        end += 1
    last = min(end, len(sequence) - 1)
    first = min(start, last)
    return sequence[first : last + 1], True, first


def _seen_during(
    game: Game,
    viewer: str,
    cell: Hex,
    frame: int,
    sequences: dict[str, list[Hex]],
    *,
    home: set[Hex] | None,
) -> bool:
    if game.rules.visibility in {"full", "total"}:
        return True
    if game.rules.visibility not in {"charted", "home"}:
        return False
    if home is not None and cell in home:
        return True
    for army in living(game, viewer):
        path = sequences.get(army.id)
        spot = path[min(frame, len(path) - 1)] if path else army.at()
        if spot is None:
            continue
        plot = None if game.plots is None else game.plots.get(spot)
        if distance(cell, spot) <= unit_gaze(army, plot):
            return True
    return False


def _event_hex(value: object) -> Hex | None:
    if not isinstance(value, dict):
        return None
    q = value.get("q")
    r = value.get("r")
    if isinstance(q, int) and isinstance(r, int):
        return Hex(q, r)
    return None


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
        "orders_locked": member.player_id in game.orders,
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
        "orders_locked": member.player_id in game.orders,
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


def _show_battle(
    game: Game,
    battle,
    viewer: str,
    staff: bool,
    *,
    home: set[Hex] | None = None,
    board: set[Hex] | None = None,
) -> bool:
    from hexcampaign.domain.terrain import has_terrain

    if viewer in battle.players or game.rules.visibility in {"full", "total"}:
        return True
    if has_terrain(game):
        if staff and battle.result is None:
            return True
    elif staff or game.rules.visibility == "full":
        return True
    # An anonymous token has no name. A battle list would put the name back.
    if not has_terrain(game) and game.rules.visibility == "anonymous":
        return False
    cell = Hex(battle.q, battle.r)
    if not known_hex(game, viewer, cell, home=home, board=board):
        return False
    involved = [army for army in game.armies if army.id in set(battle.army_ids)]
    if any(sees_army(game, viewer, army, home=home, board=board) for army in involved):
        return True
    if has_terrain(game):
        return _looking(game, viewer, cell, home=home, board=board)
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


def _chronicle(game: Game, member: bool) -> list[dict[str, object]]:
    """The story stays in the document during the war and leaves it only at the end."""
    if game.phase != "finished" or not member:
        return []
    return [dict(item) for item in game.chronicle]
