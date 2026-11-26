"""Who may enter a hex on a simultaneous step. Both marches use this."""

from dataclasses import dataclass

from hexcampaign.domain.hexes import Hex


@dataclass(frozen=True)
class DestinationClash:
    dest: Hex
    entering: tuple[str, ...]
    blocked: tuple[str, ...]
    holders: tuple[str, ...]
    fighting: tuple[str, ...]
    fight: bool


@dataclass(frozen=True)
class StepPlan:
    moving: frozenset[str]
    blocked_leavers: frozenset[str]
    origins: dict[str, Hex]
    destinations: tuple[DestinationClash, ...]


def who_can_leave(
    intended: dict[str, Hex],
    position,
    owners,
    stopped: set[str],
    kinds: dict[str, str] | None = None,
) -> set[str]:
    active = set(intended)
    while True:
        blocked = {
            army_id
            for army_id, dest in intended.items()
            if army_id in active
            and hex_stays_blocked(army_id, dest, active, position, owners, stopped, kinds)
        }
        if not blocked:
            return active
        active -= blocked


def hex_stays_blocked(
    army_id,
    dest,
    active,
    position,
    owners,
    stopped: set[str],
    kinds: dict[str, str] | None = None,
) -> bool:
    for other, cell in position.items():
        if other == army_id or cell != dest or other in active:
            continue
        if owners[other] == owners[army_id]:
            if _soft(kinds, army_id) or _soft(kinds, other):
                continue
            return True
        if other in stopped:
            return True
    return False


def without_own_stack(
    group: list[str],
    owners: dict[str, str],
    kinds: dict[str, str] | None = None,
) -> list[str]:
    crowded: set[str] = set()
    for army_id in group:
        if _soft(kinds, army_id):
            continue
        allies = [
            other
            for other in group
            if owners[other] == owners[army_id] and not _soft(kinds, other)
        ]
        if len(allies) > 1:
            crowded.add(army_id)
    return [army_id for army_id in group if army_id not in crowded]


def combatants(
    army_ids: list[str] | tuple[str, ...],
    kinds: dict[str, str] | None = None,
) -> list[str]:
    return [army_id for army_id in army_ids if not _soft(kinds, army_id)]


def plan_step(
    intended: dict[str, Hex],
    position: dict[str, Hex],
    owners: dict[str, str],
    stopped: set[str],
    kinds: dict[str, str] | None = None,
) -> StepPlan:
    """Shared leave/stack/fight planning for hex and clock marches."""
    moving = who_can_leave(intended, position, owners, stopped, kinds)
    blocked_leavers = frozenset(intended) - frozenset(moving)
    origins = {army_id: position[army_id] for army_id in moving}
    groups: dict[Hex, list[str]] = {}
    for army_id in moving:
        groups.setdefault(intended[army_id], []).append(army_id)
    destinations: list[DestinationClash] = []
    for dest, group in groups.items():
        entering = without_own_stack(group, owners, kinds)
        blocked = tuple(army_id for army_id in group if army_id not in entering)
        if not entering:
            destinations.append(
                DestinationClash(dest, (), blocked, (), (), False),
            )
            continue
        holders = tuple(
            other
            for other, cell in position.items()
            if cell == dest and other not in moving
        )
        fighting = tuple(combatants([*entering, *holders], kinds))
        fight = len({owners[army_id] for army_id in fighting}) > 1
        destinations.append(
            DestinationClash(dest, tuple(entering), blocked, holders, fighting, fight),
        )
    return StepPlan(frozenset(moving), blocked_leavers, origins, tuple(destinations))


def crossing_fighters(
    intended: dict[str, Hex],
    position: dict[str, Hex],
    owners: dict[str, str],
    kinds: dict[str, str] | None = None,
) -> list[tuple[str, str, Hex]]:
    """Enemy armies about to trade places. They stop where they already stand."""
    pairs: list[tuple[str, str, Hex]] = []
    ids = sorted(intended)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            if owners[left] == owners[right]:
                continue
            if _soft(kinds, left) or _soft(kinds, right):
                continue
            if intended[left] == position[right] and intended[right] == position[left]:
                pairs.append((left, right, position[left]))
    return pairs


def _soft(kinds: dict[str, str] | None, army_id: str) -> bool:
    return bool(kinds) and kinds.get(army_id) == "explorer"
