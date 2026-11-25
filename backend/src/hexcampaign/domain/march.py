"""Move every army at once. A shorter path arrives first and is not overtaken."""

from dataclasses import dataclass

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game
from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.sight import sees_army


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
    if game.plots is not None:
        from hexcampaign.domain.terrain_order import check_terrain_order

        check_terrain_order(game, player_id, paths)
        return
    own = [army for army in game.armies if army.player_id == player_id and not army.destroyed]
    if {army.id for army in own} != set(paths) or any(army.at() is None for army in own):
        raise DomainError("order_illegal")
    board = set(game.hexes)
    for army in own:
        path = paths[army.id]
        if len(path) > game.rules.movement:
            raise DomainError("order_illegal")
        previous = army.at()
        assert previous is not None
        for step in path:
            if step not in board or distance(previous, step) != 1:
                raise DomainError("order_illegal")
            previous = step
    sequences = {army.id: (army.at(), *paths[army.id]) for army in own}
    longest = max((len(seq) for seq in sequences.values()), default=0)
    for index in range(longest):
        seen: dict[Hex, str] = {}
        for army_id, sequence in sequences.items():
            cell = sequence[index] if index < len(sequence) else sequence[-1]
            assert cell is not None
            if cell in seen:
                raise DomainError("order_illegal")
            seen[cell] = army_id
    blocked = {
        Hex(army.q, army.r)
        for army in game.armies
        if army.player_id != player_id and sees_army(game, player_id, army)
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
) -> March:
    position = dict(starts)
    remaining = {army_id: list(paths.get(army_id, ())) for army_id in starts}
    trails: dict[str, list[Hex]] = {army_id: [] for army_id in starts}
    stopped: set[str] = set()
    contacts: list[Contact] = []

    for _ in range(max((len(path) for path in paths.values()), default=0)):
        intended = {
            army_id: steps[0]
            for army_id, steps in remaining.items()
            if steps and army_id not in stopped
        }
        if not intended:
            break
        _step_all(intended, position, remaining, trails, owners, stopped, contacts)

    return March(
        positions=position,
        trails={army_id: tuple(steps) for army_id, steps in trails.items()},
        contacts=tuple(contacts),
    )


def _step_all(intended, position, remaining, trails, owners, stopped, contacts) -> None:
    """One simultaneous step. Someone who leaves a hex does not block it."""
    moving = _who_can_leave(intended, position, owners, stopped)
    for army_id in intended:
        if army_id not in moving:
            stopped.add(army_id)
            remaining[army_id] = []
    origin = {army_id: position[army_id] for army_id in moving}
    groups: dict[Hex, list[str]] = {}
    for army_id in moving:
        groups.setdefault(intended[army_id], []).append(army_id)
    for dest, group in groups.items():
        entering = _without_own_stack(group, owners)
        for army_id in group:
            if army_id not in entering:
                stopped.add(army_id)
                remaining[army_id] = []
        if not entering:
            continue
        holders = [
            other
            for other, cell in position.items()
            if cell == dest and other not in moving
        ]
        players = {owners[army_id] for army_id in entering} | {owners[other] for other in holders}
        fight = len(players) > 1
        for army_id in entering:
            _arrive(position, trails, remaining, stopped, army_id, dest, fight=fight)
        if fight:
            contacts.append(_contact((*entering, *holders), dest))
    _fights_on_a_swap(origin, position, owners, remaining, stopped, contacts)


def _who_can_leave(intended, position, owners, stopped) -> set[str]:
    active = set(intended)
    while True:
        blocked = {
            army_id
            for army_id, dest in intended.items()
            if army_id in active
            and _hex_stays_blocked(army_id, dest, active, position, owners, stopped)
        }
        if not blocked:
            return active
        active -= blocked


def _hex_stays_blocked(army_id, dest, active, position, owners, stopped) -> bool:
    for other, cell in position.items():
        if other == army_id or cell != dest or other in active:
            continue
        if owners[other] == owners[army_id] or other in stopped:
            return True
    return False


def _without_own_stack(group: list[str], owners: dict[str, str]) -> list[str]:
    crowded = {
        army_id
        for army_id in group
        if sum(owners[other] == owners[army_id] for other in group) > 1
    }
    return [army_id for army_id in group if army_id not in crowded]


def _arrive(position, trails, remaining, stopped, army_id, dest, *, fight: bool) -> None:
    position[army_id] = dest
    trails[army_id].append(dest)
    if remaining[army_id]:
        remaining[army_id] = remaining[army_id][1:]
    if fight:
        remaining[army_id] = []
    if not remaining[army_id]:
        stopped.add(army_id)


def _fights_on_a_swap(origin, position, owners, remaining, stopped, contacts) -> None:
    seen: list[tuple[str, str]] = []
    for left, start in origin.items():
        for right, other_start in origin.items():
            if left >= right or owners[left] == owners[right]:
                continue
            if position[left] == other_start and position[right] == start:
                seen.append((left, right))
    for left, right in seen:
        for army_id in (left, right):
            remaining[army_id] = []
            stopped.add(army_id)
        contacts.append(_contact((left, right), position[left]))


def _contact(army_ids: tuple[str, ...], dest: Hex) -> Contact:
    return Contact(tuple(sorted(set(army_ids))), dest)
