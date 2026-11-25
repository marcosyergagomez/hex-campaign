"""A locked order stays secret until every required player has locked. Then the turn resolves."""

import random
from datetime import datetime

from hexcampaign.domain.board import capture, restore
from hexcampaign.domain.chronicle import cell, path, remember
from hexcampaign.domain.clock import overdue, stamp
from hexcampaign.domain.clock_march import Walker, walk
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import (
    Battle,
    Game,
    bump,
    find_army,
    find_member,
    living,
    notice,
    require_phase,
    require_player,
    require_staff,
    seated,
)
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.lobby import drop_seat_count
from hexcampaign.domain.march import check_order, march
from hexcampaign.domain.sight import gazed_cells, remember_fort


def lock_orders(
    game: Game,
    actor: str,
    paths: dict[str, list[Hex]],
    now: datetime,
    rng: random.Random | None = None,
) -> Game:
    require_phase(game, "orders")
    require_player(game, actor)
    typed = {army_id: tuple(path) for army_id, path in paths.items()}
    check_order(game, actor, typed)
    game.orders[actor] = typed
    remember(game, "orders_locked", player_id=actor)
    if _ready(game):
        return _resolve(game, now, set(), rng or random.Random())
    return bump(game)


def close_orders(
    game: Game,
    actor: str,
    now: datetime,
    rng: random.Random | None = None,
) -> Game:
    require_phase(game, "orders")
    require_staff(game, actor)
    defaulted: set[str] = set()
    for player_id in _required(game):
        if player_id in game.orders:
            continue
        defaulted.add(player_id)
        game.orders[player_id] = {army.id: () for army in living(game, player_id)}
    return _resolve(game, now, defaulted, rng or random.Random())


def report_battle(
    game: Game,
    actor: str,
    battle_id: str,
    outcome: str,
    now: datetime,
    rng: random.Random | None = None,
) -> Game:
    battle = _pending(game, battle_id)
    if overdue(battle.opened_at, game.rules.battle_days, now):
        raise DomainError("phase_invalid")
    if actor not in battle.players:
        raise DomainError("forbidden")
    battle.reports[actor] = _outcome(battle, outcome)
    remember(
        game,
        "battle_reported",
        player_id=actor,
        battle_id=battle.id,
        result=battle.reports[actor],
    )
    _agree(battle)
    _settle(game, now, rng or random.Random())
    return bump(game)


def judge_battle(
    game: Game,
    actor: str,
    battle_id: str,
    outcome: str,
    now: datetime,
    rng: random.Random | None = None,
) -> Game:
    require_staff(game, actor)
    battle = _pending(game, battle_id)
    conflict = len(battle.reports) >= 2 and len(set(battle.reports.values())) > 1
    if not conflict and not overdue(battle.opened_at, game.rules.battle_days, now):
        raise DomainError("phase_invalid")
    battle.result = _outcome(battle, outcome)
    remember(game, "battle_judged", player_id=actor, battle_id=battle.id, result=battle.result)
    _settle(game, now, rng or random.Random())
    return bump(game)


def expel_player(game: Game, actor: str, target_id: str, rng: random.Random, now: datetime) -> Game:
    require_staff(game, actor)
    target = find_member(game, target_id)
    if target is None or target.status == "expelled":
        raise DomainError("forbidden")
    if target.role == "owner" and target.status == "active":
        raise DomainError("cannot_expel_owner")
    remember(game, "expelled", player_id=actor, target_id=target.player_id)
    _remove(game, target)
    if not _active_staff(game):
        _hand_over(game, rng)
    return _after_exit(game, target.player_id, now, rng)


def leave_campaign(game: Game, actor: str, rng: random.Random, now: datetime) -> Game:
    target = find_member(game, actor)
    if target is None or target.status in {"expelled", "eliminated"}:
        raise DomainError("forbidden")
    was_owner = target.role == "owner"
    remember(game, "left", player_id=actor)
    _remove(game, target)
    if was_owner or not _active_staff(game):
        _hand_over(game, rng)
    return _after_exit(game, target.player_id, now, rng)


def promote_player(game: Game, actor: str, target_id: str) -> Game:
    require_staff(game, actor)
    require_phase(game, "placing", "orders", "battles", "finished")
    target = find_member(game, target_id)
    if target is None or target.status == "expelled":
        raise DomainError("forbidden")
    if target.role == "player":
        target.role = "admin"
        remember(game, "promoted", player_id=actor, target_id=target.player_id)
    return bump(game)


def revert_turn(game: Game, actor: str) -> Game:
    require_staff(game, actor)
    if not isinstance(game.previous, dict) or game.phase not in {"orders", "battles", "finished"}:
        raise DomainError("phase_invalid")
    undone = game.previous.get("turn", game.turn)
    restore(game, game.previous)
    remember(game, "reverted", undone=undone)
    return bump(game)


def deactivate_player(game: Game, player_id: str, rng: random.Random) -> Game:
    member = find_member(game, player_id)
    if member is None or member.status == "expelled":
        return game
    if member.status == "inactive" and member.cause == "account":
        return game
    was_owner = member.role == "owner"
    member.status = "inactive"
    member.cause = "account"
    notice(game, "player_inactive", player_id, cause="account")
    remember(game, "inactive", player_id=player_id, cause="account")
    if was_owner or not _active_staff(game):
        _hand_over(game, rng)
    return bump(game)


def _resolve(game: Game, now: datetime, defaulted: set[str], rng: random.Random) -> Game:
    game.previous = capture(game)
    starts: dict[str, Hex] = {}
    paths: dict[str, tuple[Hex, ...]] = {}
    owners: dict[str, str] = {}
    for army in living(game):
        assert army.q is not None and army.r is not None
        starts[army.id] = Hex(army.q, army.r)
        owners[army.id] = army.player_id
        paths[army.id] = game.orders.get(army.player_id, {}).get(army.id, ())
    if game.plots is None:
        moved = march(starts, paths, owners)
    else:
        moved = walk(
            [
                Walker(
                    army_id,
                    owners[army_id],
                    starts[army_id],
                    list(paths.get(army_id, ())),
                    game.rules.movement,
                    next(army.paid for army in game.armies if army.id == army_id),
                )
                for army_id in starts
            ],
            game.plots,
            set(game.hexes),
        )
    _note_marches(game, starts, paths, owners, moved)
    for army in living(game):
        cell = moved.positions[army.id]
        army.q = cell.q
        army.r = cell.r
        if game.plots is not None:
            army.paid = moved.paid[army.id]
            _reveal_gaze(game, army.player_id, moved.trails.get(army.id, ()))
        else:
            _reveal(game, army.player_id, moved.trails.get(army.id, ()))
    for contact in moved.contacts:
        _add_battle(game, contact.army_ids, contact.hex, owners, now)
    _mark_misses(game, defaulted, rng)
    if game.phase == "finished":
        game.orders = {}
        return bump(game)
    pending = [
        battle
        for battle in game.battles
        if battle.turn == game.turn and not battle.reverted and battle.result is None
    ]
    if pending:
        game.phase = "battles"
        return bump(game)
    _finish(game, now, rng)
    return bump(game)


def _settle(game: Game, now: datetime, rng: random.Random) -> None:
    if game.phase != "battles":
        return
    pending = [
        battle
        for battle in game.battles
        if battle.turn == game.turn and not battle.reverted and battle.result is None
    ]
    if pending:
        return
    for battle in game.battles:
        if battle.turn != game.turn or battle.reverted or battle.result is None:
            continue
        if battle.result != "draw":
            for army_id in battle.army_ids:
                found = find_army(game, army_id)
                if found is None or found.destroyed or found.player_id == battle.result:
                    continue
                found.destroyed = True
                remember(
                    game,
                    "destroyed",
                    player_id=found.player_id,
                    army_id=found.id,
                    name=found.name,
                    battle_id=battle.id,
                )
        remember(game, "battle_resolved", battle_id=battle.id, result=battle.result)
    _finish(game, now, rng)


def _finish(game: Game, now: datetime, rng: random.Random) -> None:
    _eliminate(game)
    _holds(game)
    winners = _winners(game)
    game.orders = {}
    if winners is not None:
        game.winners = winners
        game.phase = "finished"
        remember(game, "finished", winners=list(winners))
        return
    if not _active_staff(game):
        _hand_over(game, rng)
    if game.phase == "finished":
        return
    game.turn += 1
    game.phase = "orders"
    game.orders_opened_at = stamp(now)


def _winners(game: Game) -> list[str] | None:
    standing = [member for member in game.members if member.status in {"active", "inactive"}]
    if not standing:
        return []
    if len(standing) == 1:
        return [standing[0].player_id]
    hold: list[str] = []
    for fort in game.fortresses:
        if not fort.holder_id or fort.hold < game.rules.hold_turns or fort.holder_id in hold:
            continue
        holder = find_member(game, fort.holder_id)
        if holder is not None and holder.status in {"active", "inactive"}:
            hold.append(fort.holder_id)
    alive = [
        member.player_id
        for member in standing
        if any(army.player_id == member.player_id and not army.destroyed for army in game.armies)
    ]
    if game.rules.victory == "fortress":
        return hold or None
    if game.rules.victory == "armies":
        return alive if len(alive) == 1 else None
    if hold:
        return hold
    return alive if len(alive) == 1 else None


def _eliminate(game: Game) -> None:
    for member in game.members:
        if member.status not in {"active", "inactive"}:
            continue
        owned = [army for army in game.armies if army.player_id == member.player_id]
        if owned and all(army.destroyed for army in owned):
            member.status = "eliminated"
            member.cause = ""
            remember(game, "eliminated", player_id=member.player_id)


def _holds(game: Game) -> None:
    for fort in game.fortresses:
        enemies = [
            army
            for army in game.armies
            if not army.destroyed
            and army.q == fort.q
            and army.r == fort.r
            and army.player_id != fort.player_id
        ]
        if not enemies:
            if fort.holder_id is not None:
                remember(
                    game,
                    "hold",
                    player_id=fort.player_id,
                    holder_id="",
                    hold=0,
                    q=fort.q,
                    r=fort.r,
                )
            fort.holder_id = None
            fort.hold = 0
            continue
        same = [army for army in enemies if army.player_id == fort.holder_id]
        earliest = sorted(enemies, key=lambda army: army.id)[0]
        holder = same[0].player_id if same else earliest.player_id
        if fort.holder_id == holder:
            fort.hold += 1
        else:
            fort.holder_id = holder
            fort.hold = 1
        remember(
            game,
            "hold",
            player_id=fort.player_id,
            holder_id=holder,
            hold=fort.hold,
            q=fort.q,
            r=fort.r,
        )


def _mark_misses(game: Game, defaulted: set[str], rng: random.Random) -> None:
    hand_over = False
    for member in list(game.members):
        if member.status != "active" or member.player_id not in _required(game) | defaulted:
            continue
        if member.player_id in defaulted:
            member.missed += 1
            remember(game, "missed", player_id=member.player_id)
            if member.missed >= game.rules.missed_turns:
                was_owner = member.role == "owner"
                member.status = "inactive"
                member.cause = "missed"
                notice(game, "player_inactive", member.player_id, cause="missed")
                remember(game, "inactive", player_id=member.player_id, cause="missed")
                if was_owner or not _active_staff(game):
                    hand_over = True
            continue
        member.missed = 0
    if hand_over:
        _hand_over(game, rng)


def _required(game: Game) -> set[str]:
    # An inactive seat still has armies, so the turn waits unless an admin closes it.
    return {
        member.player_id
        for member in game.members
        if member.status in {"active", "inactive"} and living(game, member.player_id)
    }


def _ready(game: Game) -> bool:
    required = _required(game)
    return bool(required) and required <= set(game.orders)


def _note_marches(game: Game, starts, paths, owners, moved) -> None:
    names = {army.id: army.name for army in game.armies}
    for army_id, origin in starts.items():
        destination = moved.positions[army_id]
        remember(
            game,
            "marched",
            player_id=owners[army_id],
            army_id=army_id,
            name=names.get(army_id, ""),
            origin=cell(origin),
            order=path(paths.get(army_id, ())),
            trail=path(moved.trails.get(army_id, ())),
            destination=cell(destination),
        )


def _reveal(game: Game, player_id: str, cells: tuple[Hex, ...]) -> None:
    if game.rules.visibility == "full":
        game.discovered[player_id] = set(game.hexes)
        return
    known = game.discovered.setdefault(player_id, set())
    board = set(game.hexes)
    known.update(cell for cell in cells if cell in board)


def _reveal_gaze(game: Game, player_id: str, cells: tuple[Hex, ...]) -> None:
    if game.rules.visibility in {"full", "total", "charted"}:
        game.discovered[player_id] = set(game.hexes)
    else:
        known = game.discovered.setdefault(player_id, set())
        for cell in cells:
            known.update(gazed_cells(game, cell))
    for cell in cells:
        for seen in gazed_cells(game, cell):
            remember_fort(game, player_id, seen)


def _add_battle(
    game: Game,
    army_ids: tuple[str, ...],
    cell: Hex,
    owners: dict[str, str],
    now: datetime,
) -> None:
    players: list[str] = []
    for army_id in army_ids:
        player_id = owners[army_id]
        if player_id not in players:
            players.append(player_id)
    if len(players) < 2:
        return
    game.battles.append(
        Battle(
            id=f"b{game.next_id}",
            turn=game.turn,
            q=cell.q,
            r=cell.r,
            army_ids=list(army_ids),
            players=players,
            reports={},
            result=None,
            reverted=False,
            opened_at=stamp(now),
        )
    )
    game.next_id += 1
    remember(
        game,
        "battle_opened",
        battle_id=game.battles[-1].id,
        q=cell.q,
        r=cell.r,
        army_ids=list(army_ids),
        players=list(players),
    )


def _pending(game: Game, battle_id: str) -> Battle:
    found = next((battle for battle in game.battles if battle.id == battle_id), None)
    if found is None:
        raise DomainError("battle_unknown")
    if found.reverted or found.result is not None or game.phase != "battles":
        raise DomainError("battle_closed")
    return found


def _outcome(battle: Battle, outcome: str) -> str:
    if outcome == "draw" or outcome in battle.players:
        return outcome
    raise DomainError("battle_unknown")


def _agree(battle: Battle) -> None:
    if any(player_id not in battle.reports for player_id in battle.players):
        return
    values = {battle.reports[player_id] for player_id in battle.players}
    if len(values) == 1:
        battle.result = battle.reports[battle.players[0]]


def _remove(game: Game, member) -> None:
    member.status = "expelled"
    member.role = "player"
    member.cause = ""
    game.armies = [army for army in game.armies if army.player_id != member.player_id]
    game.fortresses = [fort for fort in game.fortresses if fort.player_id != member.player_id]
    game.orders.pop(member.player_id, None)
    game.discovered.pop(member.player_id, None)
    drop_seat_count(game)


def _after_exit(game: Game, player_id: str, now: datetime, rng: random.Random) -> Game:
    _release(game, player_id)
    if game.phase == "battles":
        _settle(game, now, rng)
    elif game.phase == "orders" and _ready(game):
        return _resolve(game, now, set(), rng)
    elif _campaign_over(game):
        game.phase = "finished"
        game.winners = _winners(game) or []
        game.orders = {}
        remember(game, "finished", winners=list(game.winners))
    return bump(game)


def _release(game: Game, player_id: str) -> None:
    for battle in game.battles:
        if battle.reverted or battle.result is not None or battle.turn != game.turn:
            continue
        if player_id not in battle.players:
            continue
        others = [other for other in battle.players if other != player_id]
        battle.result = others[0] if len(others) == 1 else "draw"


def _campaign_over(game: Game) -> bool:
    if game.phase in {"recruiting", "placing", "finished"}:
        return False
    return len([member for member in seated(game) if member.status != "eliminated"]) <= 1


def _hand_over(game: Game, rng: random.Random) -> None:
    owner = next((member for member in game.members if member.role == "owner"), None)
    pool = [member for member in game.members if member.status == "active"]
    if owner is not None and owner.status != "expelled":
        owner.role = "player"
    if not pool:
        game.phase = "finished"
        game.winners = []
        remember(game, "finished", winners=[])
        return
    chosen = rng.choice(sorted(pool, key=lambda member: member.player_id))
    chosen.role = "owner"
    notice(game, "owner_transferred", chosen.player_id)
    remember(game, "owner_transferred", player_id=chosen.player_id)


def _active_staff(game: Game) -> list:
    return [
        member
        for member in game.members
        if member.role in {"owner", "admin"} and member.status == "active"
    ]
