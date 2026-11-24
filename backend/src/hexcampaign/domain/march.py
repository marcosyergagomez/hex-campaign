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
    defenders = {army_id for army_id in starts if not paths.get(army_id)}
    contacts: list[Contact] = []

    for _ in range(max((len(path) for path in paths.values()), default=0)):
        movers = {
            army_id: steps[0]
            for army_id, steps in remaining.items()
            if steps and army_id not in stopped
        }
        if not movers:
            break
        handled = _exchange(movers, position, remaining, trails, owners, stopped, contacts)
        _advance(movers, handled, position, remaining, trails, owners, defenders, stopped, contacts)

    return March(
        positions=position,
        trails={army_id: tuple(steps) for army_id, steps in trails.items()},
        contacts=tuple(contacts),
    )


def _exchange(movers, position, remaining, trails, owners, stopped, contacts) -> set[str]:
    handled: set[str] = set()
    for army_id, dest in list(movers.items()):
        if army_id in handled:
            continue
        partner = _partner(army_id, dest, position, movers)
        if partner is None:
            continue
        handled.update((army_id, partner))
        _step(position, trails, remaining, army_id, dest)
        _step(position, trails, remaining, partner, movers[partner])
        if owners[army_id] == owners[partner]:
            continue
        contacts.append(_contact((army_id, partner), dest))
        stopped.update((army_id, partner))
        remaining[army_id] = []
        remaining[partner] = []
    return handled


def _advance(movers, handled, position, remaining, trails, owners, defenders, stopped, contacts):
    groups: dict[Hex, list[str]] = {}
    for army_id, dest in movers.items():
        if army_id not in handled:
            groups.setdefault(dest, []).append(army_id)
    for dest, group in groups.items():
        staying = [
            army_id
            for army_id, cell in position.items()
            if cell == dest and army_id not in group and army_id not in handled
        ]
        blocked, entering = _split(group, staying, owners, defenders)
        for army_id in blocked:
            stopped.add(army_id)
            remaining[army_id] = []
        entering = _without_stack(entering, owners)
        if not entering:
            continue
        held = [
            army_id
            for army_id in staying
            if army_id in defenders and any(owners[army_id] != owners[mover] for mover in entering)
        ]
        players = {owners[army_id] for army_id in entering}
        held_players = {owners[army_id] for army_id in held}
        if len(entering) == 1 and not held_players:
            _step(position, trails, remaining, entering[0], dest)
            continue
        if len(players | held_players) < 2:
            for army_id in entering:
                stopped.add(army_id)
                remaining[army_id] = []
            continue
        for army_id in entering:
            _step(position, trails, remaining, army_id, dest)
            stopped.add(army_id)
            remaining[army_id] = []
        contacts.append(_contact((*entering, *held), dest))


def _split(group, staying, owners, defenders) -> tuple[list[str], list[str]]:
    blocked: list[str] = []
    entering: list[str] = []
    for mover in group:
        arrived = [
            army_id
            for army_id in staying
            if owners[army_id] != owners[mover] and army_id not in defenders
        ]
        friend = [army_id for army_id in staying if owners[army_id] == owners[mover]]
        if arrived or friend:
            blocked.append(mover)
        else:
            entering.append(mover)
    return blocked, entering


def _without_stack(entering: list[str], owners: dict[str, str]) -> list[str]:
    crowded = {
        army_id
        for army_id in entering
        if sum(owners[other] == owners[army_id] for other in entering) > 1
    }
    return [army_id for army_id in entering if army_id not in crowded]


def _partner(
    army_id: str,
    dest: Hex,
    position: dict[str, Hex],
    movers: dict[str, Hex],
) -> str | None:
    here = position[army_id]
    partners = [
        other
        for other, other_dest in movers.items()
        if other != army_id and position[other] == dest and other_dest == here
    ]
    if len(partners) == 1:
        return partners[0]
    return None


def _step(position, trails, remaining, army_id: str, dest: Hex) -> None:
    position[army_id] = dest
    trails[army_id].append(dest)
    if remaining[army_id]:
        remaining[army_id] = remaining[army_id][1:]


def _contact(army_ids: tuple[str, ...], dest: Hex) -> Contact:
    return Contact(tuple(sorted(set(army_ids))), dest)
