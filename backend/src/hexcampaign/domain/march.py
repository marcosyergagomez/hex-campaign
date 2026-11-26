"""Move every army at once. A shorter path arrives first and is not overtaken."""

from dataclasses import dataclass

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.occupy import crossing_fighters, plan_step
from hexcampaign.domain.sight import sees_army
from hexcampaign.domain.units import is_explorer, move_budget


@dataclass(frozen=True)
class Contact:
    army_ids: tuple[str, ...]
    hex: Hex


@dataclass(frozen=True)
class March:
    positions: dict[str, Hex]
    trails: dict[str, tuple[Hex, ...]]
    contacts: tuple[Contact, ...]


def check_order(game: Game, player_id: str, paths: dict[str, tuple[Hex, ...]]) -> None:
    """Reject what this player can already see, including two of their armies sharing a hex."""
    from hexcampaign.domain.terrain import has_terrain

    if has_terrain(game):
        from hexcampaign.domain.terrain_order import check_terrain_order

        check_terrain_order(game, player_id, paths)
        return
    own = [army for army in game.armies if army.player_id == player_id and not army.destroyed]
    if {army.id for army in own} != set(paths) or any(army.at() is None for army in own):
        raise DomainError("order_illegal")
    board = set(game.hexes)
    forts = {fort.at() for fort in game.fortresses}
    for army in own:
        path = paths[army.id]
        if len(path) > move_budget(game.rules.movement, army):
            raise DomainError("order_illegal")
        previous = army.at()
        assert previous is not None
        for step in path:
            if step not in board or distance(previous, step) != 1:
                raise DomainError("order_illegal")
            if is_explorer(army) and step in forts:
                raise DomainError("order_illegal")
            previous = step
    sequences = {army.id: (army.at(), *paths[army.id]) for army in own}
    longest = max((len(seq) for seq in sequences.values()), default=0)
    for index in range(longest):
        seen: dict[Hex, str] = {}
        for army in own:
            if is_explorer(army):
                continue
            sequence = sequences[army.id]
            cell = sequence[index] if index < len(sequence) else sequence[-1]
            assert cell is not None
            if cell in seen:
                raise DomainError("order_illegal")
            seen[cell] = army.id
    blocked = {
        Hex(army.q, army.r)
        for army in game.armies
        if army.player_id != player_id
        and army.kind == "army"
        and sees_army(game, player_id, army)
    }
    for army in own:
        path = paths[army.id]
        for index, step in enumerate(path):
            if step in blocked and index != len(path) - 1:
                raise DomainError("order_illegal")


def march(
    starts: dict[str, Hex],
    paths: dict[str, tuple[Hex, ...]],
    owners: dict[str, str],
    kinds: dict[str, str] | None = None,
) -> March:
    position = dict(starts)
    remaining = {army_id: list(paths.get(army_id, ())) for army_id in starts}
    trails: dict[str, list[Hex]] = {army_id: [] for army_id in starts}
    stopped: set[str] = set()
    contacts: list[Contact] = []
    kinds = kinds or {army_id: "army" for army_id in starts}

    for _ in range(max((len(path) for path in paths.values()), default=0)):
        intended = {
            army_id: steps[0]
            for army_id, steps in remaining.items()
            if steps and army_id not in stopped
        }
        if not intended:
            break
        _step_all(intended, position, remaining, trails, owners, stopped, contacts, kinds)

    return March(
        positions=position,
        trails={army_id: tuple(steps) for army_id, steps in trails.items()},
        contacts=tuple(contacts),
    )


def _step_all(intended, position, remaining, trails, owners, stopped, contacts, kinds) -> None:
    """One simultaneous step. Someone who leaves a hex does not block it."""
    plan = plan_step(intended, position, owners, stopped, kinds)
    moving_intended = {army_id: intended[army_id] for army_id in plan.moving}
    crossed: set[str] = set()
    for left, right, cell in crossing_fighters(moving_intended, position, owners, kinds):
        crossed.update((left, right))
        for army_id in (left, right):
            remaining[army_id] = []
            stopped.add(army_id)
        contacts.append(_contact((left, right), cell))
    for army_id in plan.blocked_leavers:
        stopped.add(army_id)
        remaining[army_id] = []
    for clash in plan.destinations:
        for army_id in clash.blocked:
            stopped.add(army_id)
            remaining[army_id] = []
        if not clash.entering:
            continue
        for army_id in clash.entering:
            if army_id in crossed:
                continue
            _arrive(
                position,
                trails,
                remaining,
                stopped,
                army_id,
                clash.dest,
                fight=clash.fight and kinds.get(army_id) == "army",
            )
        if clash.fight and not any(army_id in crossed for army_id in clash.entering):
            contacts.append(_contact(clash.fighting, clash.dest))
            for other in clash.holders:
                if kinds.get(other) == "army":
                    remaining[other] = []
                    stopped.add(other)


def _arrive(position, trails, remaining, stopped, army_id, dest, *, fight: bool) -> None:
    position[army_id] = dest
    trails[army_id].append(dest)
    if remaining[army_id]:
        remaining[army_id] = remaining[army_id][1:]
    if fight:
        remaining[army_id] = []
    if not remaining[army_id]:
        stopped.add(army_id)


def _contact(army_ids: tuple[str, ...], dest: Hex) -> Contact:
    return Contact(tuple(sorted(set(army_ids))), dest)
