"""Armies pay to leave a hex. Until the exit is paid, they still stand on it."""

from dataclasses import dataclass, field

from hexcampaign.domain.hexes import Hex, distance
from hexcampaign.domain.march import Contact
from hexcampaign.domain.occupy import who_can_leave, without_own_stack
from hexcampaign.domain.terrain import Plot, exit_cost, passable


@dataclass
class Walker:
    army_id: str
    player_id: str
    at: Hex
    path: list[Hex]
    budget: int
    paid: int
    trail: list[Hex] = field(default_factory=list)


@dataclass(frozen=True)
class ClockMarch:
    positions: dict[str, Hex]
    trails: dict[str, tuple[Hex, ...]]
    contacts: tuple[Contact, ...]
    paid: dict[str, int]


def walk(
    walkers: list[Walker],
    plots: dict[Hex, Plot],
    board: set[Hex],
) -> ClockMarch:
    stopped: set[str] = set()
    contacts: list[Contact] = []
    by_id = {walker.army_id: walker for walker in walkers}
    span = max((len(walker.path) for walker in walkers), default=0)
    for _ in range(span * 3 + 1):
        spending = _paying(walkers, plots, board, stopped)
        if not spending:
            break
        for walker in spending:
            walker.budget -= 1
            walker.paid += 1
        ready = [walker for walker in spending if walker.paid >= exit_cost(plots[walker.at])]
        if ready:
            _step(ready, by_id, plots, stopped, contacts)
    return ClockMarch(
        positions={walker.army_id: walker.at for walker in walkers},
        trails={walker.army_id: tuple(walker.trail) for walker in walkers},
        contacts=tuple(contacts),
        paid={walker.army_id: walker.paid for walker in walkers},
    )


def _paying(walkers, plots, board, stopped) -> list[Walker]:
    spending: list[Walker] = []
    for walker in walkers:
        if walker.army_id in stopped or not walker.path or walker.budget <= 0:
            continue
        dest = walker.path[0]
        plot = plots.get(dest)
        legal = dest in board and plot is not None and passable(plot)
        if not legal or distance(walker.at, dest) != 1:
            stopped.add(walker.army_id)
            walker.path = []
            continue
        spending.append(walker)
    return spending


def _step(ready, by_id, plots, stopped, contacts) -> None:
    position = {army_id: walker.at for army_id, walker in by_id.items()}
    owners = {army_id: walker.player_id for army_id, walker in by_id.items()}
    intended = {walker.army_id: walker.path[0] for walker in ready}
    moving = who_can_leave(intended, position, owners, stopped)
    for army_id in intended:
        if army_id not in moving:
            _halt(by_id[army_id], stopped)
    origin = {army_id: position[army_id] for army_id in moving}
    groups: dict[Hex, list[str]] = {}
    for army_id in moving:
        groups.setdefault(intended[army_id], []).append(army_id)
    for dest, group in groups.items():
        entering = without_own_stack(group, owners)
        for army_id in group:
            if army_id not in entering:
                _halt(by_id[army_id], stopped)
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
            _arrive(by_id[army_id], plots, dest, stopped, fight=fight)
        if fight:
            contacts.append(Contact(tuple(sorted({*entering, *holders})), dest))
            for other in holders:
                held = by_id[other]
                held.path = []
                stopped.add(other)
    _swaps(origin, by_id, stopped, contacts)


def _arrive(walker: Walker, plots, dest: Hex, stopped: set[str], *, fight: bool) -> None:
    left = plots[walker.at]
    walker.at = dest
    walker.trail.append(dest)
    walker.path = walker.path[1:]
    walker.paid = 0
    if left.road:
        walker.budget += 1
    if fight or not walker.path:
        walker.path = []
        stopped.add(walker.army_id)


def _halt(walker: Walker, stopped: set[str]) -> None:
    walker.path = []
    stopped.add(walker.army_id)
    if walker.paid:
        walker.paid -= 1


def _swaps(origin, by_id, stopped, contacts) -> None:
    seen: list[tuple[str, str]] = []
    owners = {army_id: walker.player_id for army_id, walker in by_id.items()}
    for left, start in origin.items():
        for right, other_start in origin.items():
            if left >= right or owners[left] == owners[right]:
                continue
            if by_id[left].at == other_start and by_id[right].at == start:
                seen.append((left, right))
    for left, right in seen:
        for army_id in (left, right):
            _halt(by_id[army_id], stopped)
        contacts.append(Contact(tuple(sorted({left, right})), by_id[left].at))
