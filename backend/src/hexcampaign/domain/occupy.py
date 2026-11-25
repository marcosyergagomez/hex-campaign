"""Who may enter a hex on a simultaneous step. Both marches use this."""

from hexcampaign.domain.hexes import Hex


def who_can_leave(intended: dict[str, Hex], position, owners, stopped: set[str]) -> set[str]:
    active = set(intended)
    while True:
        blocked = {
            army_id
            for army_id, dest in intended.items()
            if army_id in active
            and hex_stays_blocked(army_id, dest, active, position, owners, stopped)
        }
        if not blocked:
            return active
        active -= blocked


def hex_stays_blocked(army_id, dest, active, position, owners, stopped: set[str]) -> bool:
    for other, cell in position.items():
        if other == army_id or cell != dest or other in active:
            continue
        if owners[other] == owners[army_id] or other in stopped:
            return True
    return False


def without_own_stack(group: list[str], owners: dict[str, str]) -> list[str]:
    crowded = {
        army_id
        for army_id in group
        if sum(owners[other] == owners[army_id] for other in group) > 1
    }
    return [army_id for army_id in group if army_id not in crowded]
