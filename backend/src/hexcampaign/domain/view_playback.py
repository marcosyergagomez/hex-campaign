"""The march film and the battles that appear in one player's view."""

from datetime import datetime

from hexcampaign.domain.clock import overdue
from hexcampaign.domain.game import Battle, Game, find_member, living
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.sight import known_hex, sees_army
from hexcampaign.domain.units import unit_gaze
from hexcampaign.domain.view_map import _looking


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

def _show_battle(
    game: Game,
    battle: Battle,
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

def _battle_view(
    game: Game,
    battle: Battle,
    viewer: str,
    staff: bool,
    now: datetime,
) -> dict[str, object]:
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
