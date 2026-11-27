"""Locked orders stay secret until the turn is ready. Then every army moves."""

import random
from datetime import datetime

from hexcampaign.domain.board import capture, restore
from hexcampaign.domain.chronicle import cell, path, remember
from hexcampaign.domain.clock import stamp
from hexcampaign.domain.clock_march import ClockMarch, Walker, walk
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import (
    Army,
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
)
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.march import March, check_order, march
from hexcampaign.domain.sight import gazed_cells, remember_fort
from hexcampaign.domain.terrain import exit_cost
from hexcampaign.domain.units import is_fighter, move_budget, unit_gaze


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


def revert_turn(game: Game, actor: str) -> Game:
    require_staff(game, actor)
    if not isinstance(game.previous, dict) or game.phase not in {"orders", "battles", "finished"}:
        raise DomainError("phase_invalid")
    undone = game.previous.get("turn", game.turn)
    restore(game, game.previous)
    remember(game, "reverted", undone=undone)
    return bump(game)

def _resolve(game: Game, now: datetime, defaulted: set[str], rng: random.Random) -> Game:
    game.previous = capture(game)
    starts: dict[str, Hex] = {}
    paths: dict[str, tuple[Hex, ...]] = {}
    owners: dict[str, str] = {}
    kinds: dict[str, str] = {}
    by_id = {army.id: army for army in living(game)}
    moved: March | ClockMarch
    for army in by_id.values():
        if army.q is None or army.r is None:
            raise DomainError("order_illegal")
        starts[army.id] = Hex(army.q, army.r)
        owners[army.id] = army.player_id
        kinds[army.id] = army.kind
        paths[army.id] = game.orders.get(army.player_id, {}).get(army.id, ())
    if game.plots is None:
        moved = march(starts, paths, owners, kinds)
    else:
        moved = walk(
            [
                Walker(
                    army_id,
                    owners[army_id],
                    starts[army_id],
                    list(paths.get(army_id, ())),
                    move_budget(game.rules.movement, by_id[army_id]),
                    by_id[army_id].paid,
                    kinds[army_id],
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
        if game.plots is not None and isinstance(moved, ClockMarch):
            army.paid = moved.paid[army.id]
            _reveal_gaze(game, army, moved.trails.get(army.id, ()))
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
    from hexcampaign.domain.departure import _active_staff, _hand_over

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
        if any(
            army.player_id == member.player_id and not army.destroyed and is_fighter(army)
            for army in game.armies
        )
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
        owned = [
            army
            for army in game.armies
            if army.player_id == member.player_id and is_fighter(army)
        ]
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
            and is_fighter(army)
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
    from hexcampaign.domain.departure import _active_staff, _hand_over

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


def _note_marches(
    game: Game,
    starts: dict[str, Hex],
    paths: dict[str, tuple[Hex, ...]],
    owners: dict[str, str],
    moved: March | ClockMarch,
) -> None:
    names = {army.id: army.name for army in game.armies}
    carried = {army.id: army.paid for army in game.armies}
    for army_id, origin in starts.items():
        destination = moved.positions[army_id]
        trail = moved.trails.get(army_id, ())
        remember(
            game,
            "marched",
            player_id=owners[army_id],
            army_id=army_id,
            name=names.get(army_id, ""),
            origin=cell(origin),
            order=path(paths.get(army_id, ())),
            trail=path(trail),
            destination=cell(destination),
            costs=_spent(game, origin, trail, carried.get(army_id, 0)),
        )


def _spent(game: Game, origin: Hex, trail: tuple[Hex, ...], paid: int) -> list[int]:
    """Points this turn actually spent to enter each hex of the trail."""
    if game.plots is None:
        return [1 for _ in trail]
    cell = origin
    spent: list[int] = []
    carried = paid
    for step in trail:
        plot = game.plots.get(cell)
        cost = 1 if plot is None else exit_cost(plot)
        spent.append(max(1, cost - carried))
        carried = 0
        cell = step
    return spent


def _reveal(game: Game, player_id: str, cells: tuple[Hex, ...]) -> None:
    if game.rules.visibility == "full":
        game.discovered[player_id] = set(game.hexes)
        return
    known = game.discovered.setdefault(player_id, set())
    board = set(game.hexes)
    known.update(cell for cell in cells if cell in board)


def _reveal_gaze(game: Game, army: Army, cells: tuple[Hex, ...]) -> None:
    player_id = army.player_id
    if game.rules.visibility in {"full", "total", "charted"}:
        game.discovered[player_id] = set(game.hexes)
    else:
        known = game.discovered.setdefault(player_id, set())
        for cell in cells:
            reach = unit_gaze(army, None if game.plots is None else game.plots.get(cell))
            known.update(gazed_cells(game, cell, reach=reach))
    for cell in cells:
        reach = unit_gaze(army, None if game.plots is None else game.plots.get(cell))
        for seen in gazed_cells(game, cell, reach=reach):
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
