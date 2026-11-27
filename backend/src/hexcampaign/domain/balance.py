"""Arrival times and map balance checks. Players lay roads after the map exists."""

import heapq
import random

from hexcampaign.domain.hexes import Hex, distance, neighbors
from hexcampaign.domain.land import initial_area, owned
from hexcampaign.domain.terrain import (
    Plot,
    exit_cost,
    gaze_from,
    passable,
    road_refund,
    terrain_groups,
)

_ORIGIN = Hex(0, 0)


def arrival_times(plots: dict[Hex, Plot], start: Hex, budget: int = 3) -> dict[Hex, int]:
    """Earliest arrival turn; a refunded road exit still needs a point to start."""
    best = {start: (1, -budget)}
    queue = [(1, -budget, start)]
    while queue:
        turn, negative_left, cell = heapq.heappop(queue)
        if best[cell] != (turn, negative_left):
            continue
        left = -negative_left
        if left == 0:
            turn, left = turn + 1, budget
        need = exit_cost(plots[cell])
        if need > left:
            unpaid = need - left
            turn += (unpaid - 1) // budget + 1
            left = budget - ((unpaid - 1) % budget + 1)
        else:
            left -= need
        # Open tracks leave the village for the eye; only rough roads repay a point.
        left += road_refund(plots[cell])
        candidate = (turn, -left)
        for other in neighbors(cell):
            if other not in plots or not passable(plots[other]):
                continue
            if candidate < best.get(other, (10**9, 0)):
                best[other] = candidate
                heapq.heappush(queue, (*candidate, other))
    return {cell: state[0] for cell, state in best.items()}


def raise_lookouts(plots: dict[Hex, Plot], forts: tuple[Hex, ...], rng: random.Random) -> bool:
    """Give each home a watch hill on the frontier. Roads are laid by players later."""
    board = set(plots)
    area = initial_area(len(board))
    for fort in forts:
        home = owned(fort, 0, board, count=area)
        outside = board - home
        lookouts = [
            cell for cell in sorted(home)
            if any(other in outside for other in neighbors(cell))
            and distance(cell, _ORIGIN) <= distance(fort, _ORIGIN)
            and plots[cell].ground in {
                "llanura", "colina", "desierto", "tundra", "montana", "campo",
            }
            and any(other in outside and passable(plots[other]) for other in neighbors(cell))
        ]
        if not lookouts:
            return False
        rng.shuffle(lookouts)
        lookout = min(lookouts, key=lambda cell: (
            gaze_from(plots[cell]) < 3, distance(cell, _ORIGIN),
        ))
        if gaze_from(plots[lookout]) < 3:
            plots[lookout] = Plot("colina")
        gates = [
            cell for cell in home
            if any(other in outside and passable(plots[other]) for other in neighbors(cell))
        ]
        if len(gates) < 3:
            return False
    return True


def road_masses(plots: dict[Hex, Plot]) -> list[set[Hex]]:
    return [
        group
        for grounds in (
            {"bosque", "bosque_profundo"}, {"montana", "colina"},
            {"pantano"}, {"tundra"},
        )
        for group in terrain_groups(plots, grounds)
    ]


def balance_problems(
    plots: dict[Hex, Plot], forts: tuple[Hex, ...],
) -> list[str]:
    board = set(plots)
    area = initial_area(len(board))
    homes = set().union(*(owned(fort, 0, board, count=area) for fort in forts))
    if any(plot.road and (cell not in homes or not passable(plot))
           for cell, plot in plots.items()):
        return ["road_outside_home"]
    if any(plots[fort].road for fort in forts):
        return ["road_on_fortress"]
    journeys = [arrival_times(plots, fort) for fort in forts]
    nearest = [
        min(times.get(other, 10**9) for other in forts if other != fort)
        for fort, times in zip(forts, journeys, strict=True)
    ]
    found: list[str] = []
    for fort in forts:
        home = owned(fort, 0, board, count=area)
        outside = board - home
        times = arrival_times({cell: plots[cell] for cell in home}, fort)
        deadline = max(2, (max(distance(cell, fort) for cell in home) + 2) // 3)
        gates = [
            cell for cell in home
            if times.get(cell, 10**9) <= deadline
            and any(other in outside and passable(plots[other]) for other in neighbors(cell))
        ]
        if len(gates) < 3 or not any(gaze_from(plots[cell]) >= 3 for cell in gates):
            found.append("home_access")
            break
    if min(nearest) < 5:
        found.append("rush")
    if max(nearest) - min(nearest) > 1:
        found.append("unequal_frontiers")
    if any(
        times.get(other, 10**9) > (distance(fort, other) + 2) // 3 + 2
        for fort, times in zip(forts, journeys, strict=True)
        for other in forts if other != fort
    ):
        found.append("long_journey")
    meeting = [
        cell for cell in board - homes
        if distance(cell, Hex(0, 0)) <= 3 and passable(plots[cell])
    ]
    if not any(
        max(times.get(cell, 10**9) for times in journeys)
        - min(times.get(cell, 10**9) for times in journeys) <= 2
        and max(times.get(cell, 10**9) for times in journeys)
        <= (2 * distance(forts[0], Hex(0, 0)) + 2) // 3 + 1
        for cell in meeting
    ):
        found.append("unequal_centre")
    return found
