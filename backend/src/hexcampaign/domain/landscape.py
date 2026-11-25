"""A landscape scales by adding bounded patches, not by inflating its obstacles."""

import heapq
import math
import random

from hexcampaign.domain.balance import arrival_times, balance_problems, local_roads
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import Hex, angle, disk, distance, neighbors
from hexcampaign.domain.land import rotate
from hexcampaign.domain.terrain import Plot, passable, terrain_groups

_ORIGIN = Hex(0, 0)
_BLOCKED = frozenset({"lago", "acantilado", "montana_rocosa"})
_RIDGE = frozenset({"montana", "montana_rocosa"})
_WOODS = frozenset({"bosque", "bosque_profundo"})


def paint(board: set[Hex], forts: tuple[Hex, ...], rng: random.Random) -> dict[Hex, Plot]:
    """Build a country. A failed sketch is thrown away and the seed continues."""
    for _ in range(64):
        plots = _sketch(board, forts, rng)
        _settle(plots, forts, rng)
        _ford(plots)
        _link(plots, board, forts)
        _single_cliffs(plots)
        if local_roads(plots, forts, rng) and not _problems(plots, board, forts):
            return plots
    raise DomainError("rules_invalid")


def _sketch(board: set[Hex], forts: tuple[Hex, ...], rng: random.Random) -> dict[Hex, Plot]:
    plots = {cell: Plot("llanura") for cell in board}
    safe = _near_forts(board, forts)
    lake_at = _inland(board, safe, rng)
    lake = _spread(board, safe, lake_at, min(24, _quota(rng, len(board), 28, 8)), rng)
    for cell in lake:
        plots[cell] = Plot("lago")
    taken = set(lake) | safe
    _rivers(plots, board, taken, lake, rng)
    _patches(plots, safe, "lago", len(board) // 30, 6, 10, rng)
    ridge = sorted(_patches(plots, safe, "montana", len(board) * 8 // 100, 6, 12, rng))
    rng.shuffle(ridge)
    for cell in ridge[::7]:
        plots[cell] = Plot("montana_rocosa")
    _patches(plots, safe, "bosque", len(board) * 27 // 100, 7, 14, rng)
    _shade(plots, rng)
    _patches(plots, safe, "colina", len(board) * 8 // 100, 3, 6, rng)
    _patches(plots, safe, "campo", len(board) * 12 // 100, 2, 4, rng)
    _dry(plots, board, rng, _quota(rng, len(board), 24, 5))
    _cold(plots, rng)
    _beach(plots, rng)
    _cliff(plots, rng)
    _marsh(plots, rng)
    _banks(plots)
    return plots


def _quota(rng: random.Random, total: int, divisor: int, floor: int) -> int:
    base = max(floor, total // divisor)
    return max(floor, int(base * rng.uniform(0.8, 1.25)))


def _near_forts(board: set[Hex], forts: tuple[Hex, ...]) -> set[Hex]:
    safe: set[Hex] = set()
    for fort in forts:
        safe.add(fort)
        safe.update(cell for cell in neighbors(fort) if cell in board)
    return safe


def _inland(board: set[Hex], safe: set[Hex], rng: random.Random) -> Hex:
    radius = max(distance(cell, _ORIGIN) for cell in board)
    reach = max(2, radius // 3)
    pool = [
        cell
        for cell in board
        if cell not in safe and 1 <= distance(cell, _ORIGIN) <= reach
    ]
    return rng.choice(pool or [cell for cell in board if cell not in safe])


def _spread(
    board: set[Hex], blocked: set[Hex], seed: Hex, count: int, rng: random.Random
) -> set[Hex]:
    blob = {seed}
    relief: dict[Hex, float] = {}
    while len(blob) < count:
        fringe = {
            cell
            for item in blob
            for cell in neighbors(item)
            if cell in board and cell not in blob and cell not in blocked
        }
        if not fringe:
            break
        for cell in sorted(fringe):
            if cell not in relief:
                relief[cell] = rng.uniform(0, 2.8)
        # Compact masses with uneven margins, without privileging an axial direction.
        blob.add(min(
            sorted(fringe),
            key=lambda cell: distance(cell, seed) + relief[cell]
            - 0.6 * sum(other in blob for other in neighbors(cell)),
        ))
    return blob


def _rivers(
    plots: dict[Hex, Plot],
    board: set[Hex],
    taken: set[Hex],
    lake: set[Hex],
    rng: random.Random,
) -> None:
    mouths = [
        cell
        for item in lake
        for cell in neighbors(item)
        if cell in board and cell not in taken
    ]
    rng.shuffle(mouths)
    target = 2 if rng.random() < 0.65 else 1
    starts: list[Hex] = []
    for _ in range(target):
        if starts:
            mouths.sort(key=lambda cell: min(distance(cell, start) for start in starts),
                        reverse=True)
        for mouth in mouths:
            if mouth in taken:
                continue
            course = _upstream(board, taken, lake, mouth, rng, _quota(rng, len(board), 18, 10))
            if course is None:
                continue
            for cell in course:
                plots[cell] = Plot("rio")
                taken.add(cell)
            starts.append(mouth)
            break


def _upstream(
    board: set[Hex],
    taken: set[Hex],
    lake: set[Hex],
    mouth: Hex,
    rng: random.Random,
    length: int,
) -> list[Hex] | None:
    path = [mouth]
    heading = _away_step(mouth, lake, board, taken)
    if heading is None:
        return None
    while len(path) < length:
        if _rim(path[-1], board) and len(path) >= 6:
            break
        nxt, heading = _step_away(path, heading, board, taken, lake, rng)
        if nxt is None or heading is None:
            break
        path.append(nxt)
    if len(path) < 6 or not _rim(path[-1], board):
        return None
    if not any(cell in lake for cell in neighbors(path[0])):
        return None
    return path


def _away_step(
    mouth: Hex,
    lake: set[Hex],
    board: set[Hex],
    taken: set[Hex],
) -> Hex | None:
    options = [cell for cell in neighbors(mouth) if cell in board and cell not in taken]
    if not options:
        return None
    away = max(options, key=lambda cell: _clearance(cell, lake))
    return Hex(away.q - mouth.q, away.r - mouth.r)


def _step_away(
    path: list[Hex],
    heading: Hex,
    board: set[Hex],
    taken: set[Hex],
    lake: set[Hex],
    rng: random.Random,
) -> tuple[Hex | None, Hex | None]:
    ranked: list[tuple[float, Hex, Hex]] = []
    for twist in (0, 1, -1, 2, -2):
        step = rotate(heading, twist)
        nxt = Hex(path[-1].q + step.q, path[-1].r + step.r)
        if nxt not in board or nxt in taken or nxt in path:
            continue
        if any(other in path[:-1] for other in neighbors(nxt)):
            continue
        score = _clearance(nxt, lake) + rng.uniform(0, 2.5)
        ranked.append((score, nxt, step))
    if not ranked:
        return None, None
    ranked.sort(key=lambda item: item[0], reverse=True)
    _, nxt, step = rng.choice(ranked[: min(2, len(ranked))])
    if rng.random() < 0.3:
        step = rotate(step, rng.choice((1, -1)))
    return nxt, step


def _clearance(cell: Hex, lake: set[Hex]) -> int:
    return min(distance(cell, drop) for drop in lake)


def _patches(
    plots: dict[Hex, Plot],
    safe: set[Hex],
    ground: str,
    target: int,
    low: int,
    high: int,
    rng: random.Random,
) -> set[Hex]:
    family = _RIDGE | {"colina"} if ground in {"montana", "colina"} else {ground}
    blocked = set(safe)
    for cell, plot in plots.items():
        if plot.ground in family:
            blocked.update(neighbors(cell))
    planted: set[Hex] = set()
    centres: list[Hex] = []
    offsets = disk(19)
    while len(planted) < target:
        available = {cell for cell, plot in plots.items()
                     if plot.ground == "llanura" and cell not in blocked}
        seeds = sorted(available)
        rng.shuffle(seeds)
        if centres:
            seeds.sort(
                key=lambda cell: min(distance(cell, centre) for centre in centres), reverse=True,
            )
        for seed in seeds:
            window = {Hex(seed.q + step.q, seed.r + step.r) for step in offsets} & available
            need = min(low, target - len(planted))
            if len(window) < need:
                continue
            count = min(rng.randint(low, high), target - len(planted), len(window))
            grown = _spread(window, set(), seed, count, rng)
            if len(grown) < need:
                continue
            for cell in grown:
                plots[cell] = Plot(ground)
                blocked.update(neighbors(cell))
            planted.update(grown)
            centres.append(seed)
            break
        else:
            break
    return planted


def _shade(plots: dict[Hex, Plot], rng: random.Random) -> None:
    deep = [
        cell
        for cell, plot in plots.items()
        if plot.ground == "bosque" and _wooded(plots, cell) >= 4
    ]
    rng.shuffle(deep)
    for cell in deep[: max(2, len(deep) // 3)]:
        if _wooded(plots, cell) >= 3:
            plots[cell] = Plot("bosque_profundo")


def _wooded(plots: dict[Hex, Plot], cell: Hex) -> int:
    return sum(plots[other].ground == "bosque" for other in neighbors(cell) if other in plots)


def _dry(plots: dict[Hex, Plot], board: set[Hex], rng: random.Random, count: int) -> None:
    woods = {cell for cell, plot in plots.items() if plot.ground in _WOODS}
    if not woods:
        return
    pool = [
        cell
        for cell, plot in plots.items()
        if plot.ground == "llanura" and min(distance(cell, tree) for tree in woods) >= 3
    ]
    if not pool:
        return
    seed = rng.choice(pool)
    for cell in _spread(board, set(board) - set(pool), seed, count, rng):
        plots[cell] = Plot("desierto")


def _cold(plots: dict[Hex, Plot], rng: random.Random) -> None:
    cold = [
        cell
        for cell, plot in plots.items()
        if plot.ground in {"llanura", "colina"}
        and any(
            plots[other].ground == "montana_rocosa"
            for other in neighbors(cell)
            if other in plots
        )
    ]
    rng.shuffle(cold)
    for cell in cold[: max(3, len(cold) // 2)]:
        plots[cell] = Plot("tundra")


def _beach(plots: dict[Hex, Plot], rng: random.Random) -> None:
    chain = _longest_shore(plots, {"llanura", "colina"})
    if len(chain) < 2:
        return
    high = min(7, len(chain))
    for cell in chain[: rng.randint(min(3, high), high)]:
        plots[cell] = Plot("playa")


def _cliff(plots: dict[Hex, Plot], rng: random.Random) -> None:
    chain = _longest_shore(plots, {"llanura", "colina", "desierto", "tundra"})
    if len(chain) < 2:
        return
    high = min(5, len(chain))
    for cell in chain[: rng.randint(min(3, high), high)]:
        plots[cell] = Plot("acantilado")


def _longest_shore(plots: dict[Hex, Plot], grounds: set[str]) -> list[Hex]:
    shore = _shore(plots, grounds)
    best: list[Hex] = []
    for start in shore:
        chain = _walk(shore, start, len(shore))
        if len(chain) > len(best):
            best = chain
    return best


def _marsh(plots: dict[Hex, Plot], rng: random.Random) -> None:
    wet = [
        cell
        for cell, plot in plots.items()
        if plot.ground == "llanura" and _touches(plots, cell, "rio", "orilla", "lago")
    ]
    rng.shuffle(wet)
    for cell in wet[:3]:
        plots[cell] = Plot("pantano")


def _banks(plots: dict[Hex, Plot]) -> None:
    for cell, plot in list(plots.items()):
        if plot.ground == "llanura" and _touches(plots, cell, "rio"):
            plots[cell] = Plot("orilla")


def _shore(plots: dict[Hex, Plot], grounds: set[str]) -> list[Hex]:
    return [
        cell
        for cell, plot in plots.items()
        if plot.ground in grounds and _touches(plots, cell, "lago")
    ]


def _walk(shore: list[Hex], start: Hex, count: int) -> list[Hex]:
    allowed = set(shore)
    chain = [start]
    while len(chain) < count:
        nxt = [
            cell
            for cell in neighbors(chain[-1])
            if cell in allowed and cell not in chain
        ]
        if not nxt:
            break
        chain.append(min(nxt))
    return chain


def _settle(plots: dict[Hex, Plot], forts: tuple[Hex, ...], rng: random.Random) -> None:
    for fort in forts:
        plots[fort] = Plot("llanura")
        ring = [cell for cell in neighbors(fort) if cell in plots]
        for cell in ring:
            if not passable(plots[cell]) or plots[cell].ground == "rio":
                plots[cell] = Plot("llanura")
        rng.shuffle(ring)
        if ring:
            plots[ring[0]] = Plot("campo")
        if len(ring) > 1:
            plots[ring[1]] = Plot("mina")
        if len(ring) > 2:
            plots[ring[2]] = Plot("colina")


def _ford(plots: dict[Hex, Plot]) -> None:
    for cell, plot in plots.items():
        if plot.ground != "rio":
            continue
        sides = [
            other
            for other in neighbors(cell)
            if other in plots and passable(plots[other]) and plots[other].ground != "rio"
        ]
        if len(sides) >= 2:
            plots[cell] = Plot("rio", bridge=True)
            return


def _link(plots: dict[Hex, Plot], board: set[Hex], forts: tuple[Hex, ...]) -> None:
    for goal in forts[1:]:
        if goal in _region(plots, forts[0]):
            continue
        path = _widen(plots, board, forts[0], goal)
        for cell in path:
            if plots[cell].ground in _BLOCKED:
                plots[cell] = Plot("llanura")


def _widen(plots: dict[Hex, Plot], board: set[Hex], start: Hex, goal: Hex) -> list[Hex]:
    weight = {"lago": 40, "acantilado": 8, "montana_rocosa": 8}
    cost: dict[Hex, int] = {start: 0}
    previous: dict[Hex, Hex | None] = {start: None}
    queue = [(0, start.q, start.r, start)]
    while queue:
        spent, _, _, cell = heapq.heappop(queue)
        if spent != cost[cell]:
            continue
        if cell == goal:
            break
        for other in neighbors(cell):
            if other not in board:
                continue
            step = spent + weight.get(plots[other].ground, 1)
            if step < cost.get(other, 10**9):
                cost[other] = step
                previous[other] = cell
                heapq.heappush(queue, (step, other.q, other.r, other))
    path: list[Hex] = []
    cursor: Hex | None = goal if goal in previous else None
    while cursor is not None:
        path.append(cursor)
        cursor = previous[cursor]
    return path


def _single_cliffs(plots: dict[Hex, Plot]) -> None:
    for cell, plot in list(plots.items()):
        if plot.ground != "acantilado":
            continue
        joined = any(
            plots[other].ground == "acantilado" for other in neighbors(cell) if other in plots
        )
        if not joined:
            plots[cell] = Plot("colina")


def _problems(plots: dict[Hex, Plot], board: set[Hex], forts: tuple[Hex, ...]) -> list[str]:
    found: list[str] = []
    sectors: list[list[Plot]] = [[] for _ in range(6)]
    for cell, plot in plots.items():
        sectors[int((angle(cell) + math.pi) * 3 / math.pi) % 6].append(plot)
    if any(sum(plot.ground not in {"llanura", "desierto", "playa", "tundra"}
               for plot in sector) * 3 < len(sector) for sector in sectors):
        found.append("empty_sector")
    if sum(plot.ground in _WOODS for plot in plots.values()) < len(board) * .23:
        found.append("forest_density")
    if sum(plot.ground == "campo" for plot in plots.values()) < len(board) * .07:
        found.append("fields_density")
    for grounds in (_WOODS, frozenset({"montana", "colina"})):
        for group in terrain_groups(plots, grounds):
            terrain = {cell: plots[cell] for cell in group}
            if len(group) > 18 or any(
                max(arrival_times(terrain, start).values()) > 4 for start in group
            ):
                found.append("slow_mass")
                break
    if _largest(plots, {"lago"}) < 6:
        found.append("lake")
    if _course(plots) < 6:
        found.append("river")
    if _largest(plots, _WOODS) < 8:
        found.append("forest")
    if _largest(plots, _RIDGE) < 5:
        found.append("ridge")
    if any(not passable(plots[fort]) for fort in forts):
        found.append("fort")
    reached = _region(plots, forts[0])
    if any(fort not in reached for fort in forts):
        found.append("cut")
    if not _rivers_ok(plots, board):
        found.append("course")
    if not _shores_ok(plots, board):
        found.append("shore")
    if not found:
        found.extend(balance_problems(plots, forts))
    return found


def _rivers_ok(plots: dict[Hex, Plot], board: set[Hex]) -> bool:
    for group in terrain_groups(plots, {"rio"}):
        if len(group) < 2 or not _is_path(group):
            return False
        tips = [cell for cell in group if _degree(cell, group) == 1]
        for tip in tips:
            wet = _touches(plots, tip, "lago")
            if not wet and not _rim(tip, board):
                return False
    return True


def _shores_ok(plots: dict[Hex, Plot], board: set[Hex]) -> bool:
    for cell, plot in plots.items():
        if plot.ground == "orilla" and not _touches(plots, cell, "rio"):
            return False
        if plot.ground == "playa" and not (_touches(plots, cell, "lago") or _rim(cell, board)):
            return False
        if plot.ground == "pantano" and not _touches(plots, cell, "rio", "orilla", "lago"):
            return False
        if plot.ground == "bosque_profundo" and not _touches(plots, cell, "bosque"):
            return False
        if plot.ground == "acantilado":
            rocky = any(
                plots[other].ground == "acantilado" for other in neighbors(cell) if other in plots
            )
            if not rocky or not (_touches(plots, cell, "lago") or _rim(cell, board)):
                return False
        if plot.bridge:
            sides = [
                other
                for other in neighbors(cell)
                if other in plots and passable(plots[other])
            ]
            if len(sides) < 2:
                return False
    return True


def _course(plots: dict[Hex, Plot]) -> int:
    groups = terrain_groups(plots, {"rio"})
    return max((len(group) for group in groups), default=0)


def _largest(plots: dict[Hex, Plot], grounds: frozenset[str] | set[str]) -> int:
    groups = terrain_groups(plots, grounds)
    return max((len(group) for group in groups), default=0)


def _region(plots: dict[Hex, Plot], start: Hex) -> set[Hex]:
    reached = {start}
    queue = [start]
    while queue:
        cell = queue.pop()
        for other in neighbors(cell):
            if other in plots and other not in reached and passable(plots[other]):
                reached.add(other)
                queue.append(other)
    return reached


def _is_path(group: set[Hex]) -> bool:
    degrees = sorted(_degree(cell, group) for cell in group)
    return degrees == [1, 1] + [2] * (len(group) - 2)


def _degree(cell: Hex, group: set[Hex]) -> int:
    return sum(other in group for other in neighbors(cell))


def _touches(plots: dict[Hex, Plot], cell: Hex, *grounds: str) -> bool:
    return any(other in plots and plots[other].ground in grounds for other in neighbors(cell))


def _rim(cell: Hex, board: set[Hex]) -> bool:
    return any(other not in board for other in neighbors(cell))
