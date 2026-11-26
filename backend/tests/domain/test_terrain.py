"""Exit costs, the home disk, and the point clock. No database."""

import heapq
import math
import random
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from hexcampaign.domain.balance import arrival_times, balance_problems
from hexcampaign.domain.clock_march import Walker, walk
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import from_dict, to_dict
from hexcampaign.domain.hexes import Hex, angle, disk, distance, neighbors
from hexcampaign.domain.land import home_radius, owned, rotate
from hexcampaign.domain.landscape import _problems, _spread
from hexcampaign.domain.game import seated
from hexcampaign.domain.lobby import accept_seat, begin, change_rules, create_game, mark_ready
from hexcampaign.domain.map_document import dump_template, load_template
from hexcampaign.domain.maps import Template, generate, lay
from hexcampaign.domain.roads import finish_roads, road_budget
from hexcampaign.domain.rules import rules_from
from hexcampaign.domain.sight import remember_fort
from hexcampaign.domain.terrain import (
    HOME_RADIUS,
    Plot,
    checked_plot,
    exit_cost,
    gaze_from,
    passable,
    terrain_groups,
)
from hexcampaign.domain.turn import lock_orders
from hexcampaign.domain.view import project, project_roads_delta

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _leave_forts(game, now=NOW):
    if game.plots is None or not game.fort_open:
        return game
    from hexcampaign.domain.lobby import confirm_placement, place_armies

    players = seated(game)
    for index, member in enumerate(players):
        if member.status != "active" or member.player_id in game.lobby_ready:
            continue
        if not any(fort.player_id == member.player_id for fort in game.fortresses):
            fort = game.anchors[index]
            board = set(game.hexes)
            blocked = {item.at() for item in game.fortresses}
            blocked.add(fort)
            ring = [
                cell for cell in neighbors(fort)
                if cell in board and cell not in blocked and passable(game.plots[cell])
            ]
            own = [
                army for army in game.armies
                if army.player_id == member.player_id and not army.destroyed
            ]
            spots = {}
            cursor = 0
            for army in own:
                if army.kind == "army" and fort not in spots.values():
                    spots[army.id] = fort
                else:
                    spots[army.id] = ring[cursor]
                    cursor += 1
            place_armies(game, member.player_id, fort, spots)
        confirm_placement(game, member.player_id, now)
    return game


def _finish_prep(game, now=NOW):
    if game.phase != "preparing":
        return game
    from hexcampaign.domain.lobby import describe_army

    _leave_forts(game, now)
    if game.plots is None or game.phase != "preparing":
        return game
    for member in seated(game):
        if member.status == "active" and member.player_id not in game.road_ready:
            finish_roads(game, member.player_id, now)
    if game.phase != "preparing":
        return game
    for army in game.armies:
        if army.destroyed or army.at() is not None:
            continue
        fort = next(item for item in game.fortresses if item.player_id == army.player_id)
        army.q, army.r = fort.q, fort.r
    for member in seated(game):
        if member.status != "active" or member.player_id in game.prep_done:
            continue
        for army in list(game.armies):
            if army.player_id != member.player_id or army.kind != "army" or army.destroyed:
                continue
            if army.commander:
                continue
            roster = "lista" if game.rules.roster_required else ""
            describe_army(
                game,
                member.player_id,
                army.id,
                army.name,
                f"{member.alias} {army.id}",
                army.race,
                roster,
                now,
            )
    return game


def _ready_table(game):
    for member in seated(game):
        if member.status == "active":
            mark_ready(game, member.player_id)
    return game


def test_territory_owners_are_only_sent_for_known_cells_and_respect_the_saved_area() -> None:
    rules = rules_from({
        "seats": 2, "armies": 1, "movement": 3, "map_size": 61, "visibility": "full",
        "victory": "armies", "hold_turns": 3, "placement": "app",
        "order_days": 7, "battle_days": 7, "missed_turns": 2,
    })
    game = create_game("Colores", rules, "1", "ana")
    accept_seat(game, "2", "boa")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    begin(_ready_table(game), "1", [], now)
    game.plots = {cell: Plot("llanura") for cell in game.hexes}
    game.home_size = 7
    game.rules = replace(game.rules, visibility="home")
    game.discovered = {}
    body = project(game, "1", now)
    known = [cell for cell in body["hexes"] if cell["known"]]
    assert len(known) == 7
    assert all(cell["owner_id"] == "1" for cell in known)
    assert all(set(cell) == {"q", "r", "known"} for cell in body["hexes"] if not cell["known"])
    rival = next(fort for fort in game.fortresses if fort.player_id == "2")
    edge = next(
        cell for cell in owned(rival.at(), 1, set(game.hexes), count=7) if cell != rival.at()
    )
    game.discovered["1"] = {edge}
    revealed = project(game, "1", now)
    shown = next(cell for cell in revealed["hexes"] if (cell["q"], cell["r"]) == (edge.q, edge.r))
    assert shown["owner_id"] == "2"
    assert all(fort["player_id"] != "2" for fort in revealed["fortresses"])
    game.rules = replace(game.rules, visibility="total")
    total = project(game, "1", now)
    assert sum(cell["owner_id"] == "1" for cell in total["hexes"]) == 7
    assert sum(cell["owner_id"] == "2" for cell in total["hexes"]) == 7
    assert any(cell["owner_id"] is None for cell in total["hexes"])


def test_a_road_makes_the_exit_cost_one_and_a_hill_looks_one_farther() -> None:
    assert exit_cost(Plot("llanura")) == 1
    assert exit_cost(Plot("bosque_profundo")) == 3
    assert exit_cost(Plot("montana", road=True)) == 1
    assert exit_cost(Plot("rio", bridge=True)) == 1
    assert gaze_from(Plot("llanura")) == 2
    assert gaze_from(Plot("colina")) == 3
    assert gaze_from(Plot("montana")) == 4
    assert gaze_from(Plot("bosque_profundo")) == 0


def test_a_bridge_only_stands_on_a_river_and_a_road_does_not_cross_a_cliff() -> None:
    with pytest.raises(DomainError):
        checked_plot("acantilado", True, False)
    with pytest.raises(DomainError):
        checked_plot("llanura", False, True)


def test_home_disks_grow_with_the_map_and_do_not_cover_a_large_one() -> None:
    assert HOME_RADIUS[19] == 1
    assert HOME_RADIUS[37] == 1
    assert HOME_RADIUS[61] == 2
    assert HOME_RADIUS[271] == 2
    assert HOME_RADIUS[397] == 2
    assert HOME_RADIUS[547] == 3
    board = {Hex(q, r) for q in range(-4, 5) for r in range(-4, 5)}
    home = owned(Hex(4, 0), 2, board)
    assert Hex(4, 0) in home
    assert Hex(0, 0) not in home


def test_three_turns_of_a_sixth_bring_a_hex_back_to_itself() -> None:
    cell = Hex(4, -1)
    assert rotate(rotate(rotate(cell, 2), 2), 2) == cell
    assert rotate(cell, 3) == Hex(-4, 1)


def test_three_points_stop_inside_the_deep_forest_still_owing_one() -> None:
    plains = Hex(0, 0)
    deep = Hex(1, 0)
    beyond = Hex(2, 0)
    plots = {
        plains: Plot("llanura"),
        deep: Plot("bosque_profundo"),
        beyond: Plot("llanura"),
    }
    walker = Walker("a", "p", plains, [deep, beyond], budget=3, paid=0)
    moved = walk([walker], plots, set(plots))
    assert moved.positions["a"] == deep
    assert moved.paid["a"] == 2


def test_three_points_do_leave_an_ordinary_forest() -> None:
    plains = Hex(0, 0)
    wood = Hex(1, 0)
    beyond = Hex(2, 0)
    plots = {plains: Plot("llanura"), wood: Plot("bosque"), beyond: Plot("llanura")}
    walker = Walker("a", "p", plains, [wood, beyond], budget=3, paid=0)
    moved = walk([walker], plots, set(plots))
    assert moved.positions["a"] == beyond
    assert moved.paid["a"] == 0


def test_a_walker_stops_before_an_impassable_hex() -> None:
    start = Hex(0, 0)
    cliff = Hex(1, 0)
    plots = {start: Plot("llanura"), cliff: Plot("acantilado")}
    walker = Walker("a", "p", start, [cliff], budget=3, paid=0)

    moved = walk([walker], plots, set(plots))

    assert moved.positions["a"] == start
    assert moved.trails["a"] == ()


def test_enemy_armies_stop_instead_of_passing_through_each_other() -> None:
    start = Hex(0, 0)
    middle = Hex(1, 0)
    hill = Hex(2, 0)
    plots = {
        start: Plot("desierto"),
        middle: Plot("desierto"),
        hill: Plot("colina"),
    }
    plain = Walker("a", "1", start, [middle, hill], budget=4, paid=0)
    slow = Walker("b", "2", hill, [middle], budget=4, paid=0)

    moved = walk([plain, slow], plots, set(plots))

    assert moved.positions["a"] == middle
    assert moved.positions["b"] == hill
    assert [contact.army_ids for contact in moved.contacts] == [("a", "b")]


def test_the_army_that_leaves_a_plain_reaches_the_hex_before_the_one_on_a_hill() -> None:
    target = Hex(1, 0)
    plots = {
        Hex(0, 0): Plot("llanura"),
        Hex(1, -1): Plot("colina"),
        target: Plot("llanura"),
    }
    plain = Walker("a", "ana", Hex(0, 0), [target], budget=3, paid=0)
    hill = Walker("b", "boa", Hex(1, -1), [target], budget=3, paid=0)
    moved = walk([plain, hill], plots, set(plots))
    assert moved.positions["a"] == target
    assert moved.positions["b"] == Hex(1, -1)
    assert moved.contacts == ()


def test_two_exits_of_the_same_cost_open_a_battle() -> None:
    target = Hex(1, 0)
    plots = {Hex(0, 0): Plot("llanura"), Hex(2, 0): Plot("llanura"), target: Plot("llanura")}
    left = Walker("a", "ana", Hex(0, 0), [target], budget=1, paid=0)
    right = Walker("b", "boa", Hex(2, 0), [target], budget=1, paid=0)
    moved = walk([left, right], plots, set(plots))
    assert moved.positions["a"] == target
    assert moved.positions["b"] == target
    assert moved.contacts[0].hex == target
    assert moved.contacts[0].army_ids == ("a", "b")


def test_an_unseen_cliff_stops_the_army_without_charging_the_exit() -> None:
    start = Hex(0, 0)
    cliff = Hex(1, 0)
    plots = {start: Plot("llanura"), cliff: Plot("acantilado")}
    walker = Walker("a", "p", start, [cliff], budget=3, paid=0)
    moved = walk([walker], plots, set(plots))
    assert moved.positions["a"] == start
    assert moved.paid["a"] == 0


def test_a_saved_payment_finishes_the_exit_on_the_next_turn() -> None:
    deep = Hex(0, 0)
    plains = Hex(1, 0)
    plots = {deep: Plot("bosque_profundo"), plains: Plot("llanura")}
    walker = Walker("a", "p", deep, [plains], budget=1, paid=2)
    moved = walk([walker], plots, set(plots))
    assert moved.positions["a"] == plains
    assert moved.paid["a"] == 0


def test_movement_two_needs_two_turns_to_leave_deep_woods() -> None:
    deep = Hex(0, 0)
    plains = Hex(1, 0)
    plots = {deep: Plot("bosque_profundo"), plains: Plot("llanura")}
    first = walk([Walker("a", "p", deep, [plains], budget=2, paid=0)], plots, set(plots))
    assert first.positions["a"] == deep
    assert first.paid["a"] == 2
    second = walk(
        [Walker("a", "p", deep, [plains], budget=2, paid=first.paid["a"])],
        plots,
        set(plots),
    )
    assert second.positions["a"] == plains
    assert second.paid["a"] == 0


def test_leaving_by_a_road_pays_for_one_more_plain() -> None:
    first = Hex(0, 0)
    second = Hex(1, 0)
    third = Hex(2, 0)
    plots = {first: Plot("bosque", road=True), second: Plot("llanura"), third: Plot("llanura")}
    walker = Walker("a", "p", first, [second, third], budget=1, paid=0)
    moved = walk([walker], plots, set(plots))
    assert moved.positions["a"] == third


def test_an_open_track_does_not_repay_movement() -> None:
    first = Hex(0, 0)
    second = Hex(1, 0)
    third = Hex(2, 0)
    plots = {first: Plot("llanura", road=True), second: Plot("llanura"), third: Plot("llanura")}
    walker = Walker("a", "p", first, [second, third], budget=1, paid=0)
    moved = walk([walker], plots, set(plots))
    assert moved.positions["a"] == second


@pytest.mark.parametrize("budget", [1, 2, 3])
def test_arrival_estimates_match_the_movement_engine_with_refunds_and_carried_payments(
    budget: int,
) -> None:
    cells = [Hex(q, 0) for q in range(9)]
    grounds = [
        Plot("llanura"), Plot("bosque", road=True), Plot("colina", road=True),
        Plot("bosque_profundo"), Plot("llanura"), Plot("montana", road=True),
        Plot("montana"), Plot("llanura"), Plot("llanura"),
    ]
    plots = dict(zip(cells, grounds, strict=True))
    times = arrival_times(plots, cells[0], budget)
    for index, goal in enumerate(cells[1:], 1):
        at, paid, turn = cells[0], 0, 0
        while at != goal:
            turn += 1
            path = cells[cells.index(at) + 1:index + 1]
            moved = walk([Walker("a", "p", at, path, budget, paid)], plots, set(cells))
            at, paid = moved.positions["a"], moved.paid["a"]
        assert times[goal] == turn
    blocked = Hex(0, 1)
    plots[blocked] = Plot("montana_rocosa")
    assert blocked not in arrival_times(plots, cells[0], budget)


def test_local_roads_must_not_turn_a_long_geometric_separation_into_a_rush() -> None:
    plots = {cell: Plot("llanura") for cell in disk(271)}
    forts = (Hex(7, 0), Hex(-7, 0))
    plots[Hex(6, 0)] = Plot("bosque", road=True)
    plots[Hex(5, 0)] = Plot("bosque", road=True)
    plots[Hex(-6, 0)] = Plot("bosque", road=True)
    assert _turns(plots, *forts) == 4
    assert "rush" in balance_problems(plots, forts)
    plots[Hex(0, 0)] = Plot("bosque", road=True)
    assert "road_outside_home" in balance_problems(plots, forts)


def _table(**overrides: object):
    data: dict[str, object] = {
        "seats": 2,
        "armies": 1,
        "movement": 1,
        "map_size": 19,
        "visibility": "home",
        "victory": "armies",
        "hold_turns": 3,
        "placement": "players",
        "order_days": 7,
        "battle_days": 7,
        "missed_turns": 2,
    }
    data.update(overrides)
    return rules_from(data)


def test_two_seeds_lay_different_countries() -> None:
    first = generate(271, 2, random.Random(1))
    second = generate(271, 2, random.Random(2))
    left = [plot.ground for _, plot in sorted(first.cells.items())]
    right = [plot.ground for _, plot in sorted(second.cells.items())]
    assert sum(item != other for item, other in zip(left, right, strict=True)) > 40


def test_land_masses_grow_around_their_seed_with_varied_contours() -> None:
    board = {Hex(q, r) for q in range(-10, 11) for r in range(-10, 11)}
    seed = Hex(0, 0)
    first = _spread(board, set(), seed, 25, random.Random(1))
    assert first == _spread(board, set(), seed, 25, random.Random(1))
    assert first != _spread(board, set(), seed, 25, random.Random(2))
    assert len(first) == 25
    assert max(distance(cell, seed) for cell in first) <= 5
    assert any(cell.q > 0 for cell in first)
    assert any(cell.q < 0 for cell in first)
    blocked = {Hex(1, 0), Hex(0, 1)}
    assert _spread(board, blocked, seed, 25, random.Random(1)).isdisjoint(blocked)


@pytest.mark.parametrize(
    ("size", "seats"),
    [
        (271, 2), (271, 3), (397, 2), (397, 3), (397, 4),
        (547, 2), (547, 3), (547, 4),
    ],
)
def test_natural_contours_preserve_generated_geography(size: int, seats: int) -> None:
    for seed in range(12):
        template = generate(size, seats, random.Random(seed))
        assert not _problems(template.cells, set(template.cells), template.anchors)
        assert sum(plot.ground == "llanura" for plot in template.cells.values()) / size < 0.5
        assert sum(
            plot.ground in {"bosque", "bosque_profundo"} for plot in template.cells.values()
        ) / size >= 0.23
        homes = set()
        nearest = []
        for fort in template.anchors:
            home = owned(fort, HOME_RADIUS[size], set(template.cells), count=template.home_size)
            assert len(home) == template.home_size
            assert homes.isdisjoint(home)
            homes.update(home)
            times = arrival_times({cell: template.cells[cell] for cell in home}, fort)
            gates = {
                cell for cell in home
                if times.get(cell, 10**9) <= 2
                and any(other in template.cells and other not in home
                        and passable(template.cells[other]) for other in neighbors(cell))
            }
            assert len(gates) >= 3
            assert any(gaze_from(template.cells[cell]) >= 3 for cell in gates)
            assert all(not template.cells[cell].road for cell in home)
            times = arrival_times(template.cells, fort)
            assert all(
                5 <= times[other] <= math.ceil(distance(fort, other) / 3) + 2
                for other in template.anchors if other != fort
            )
            nearest.append(min(times[other] for other in template.anchors if other != fort))
        assert min(nearest) >= 5
        assert max(nearest) - min(nearest) <= 1
        assert all(not plot.road for plot in template.cells.values())


@pytest.mark.parametrize(("size", "seats"), [(331, 3), (469, 4), (631, 4)])
def test_unlisted_sizes_create_bounded_masses_and_populated_regions(size: int, seats: int) -> None:
    template = generate(size, seats, random.Random(17))
    assert len(template.cells) == size
    assert not _problems(template.cells, set(template.cells), template.anchors)
    forests = terrain_groups(template.cells, {"bosque", "bosque_profundo"})
    assert len(forests) >= math.ceil(size * .23 / 18)
    for group in forests:
        assert len(group) <= 18
        ground = {cell: template.cells[cell] for cell in group}
        for start in group:
            assert max(arrival_times(ground, start, 3).values()) <= 4
    for sector in range(6):
        plots = [plot for cell, plot in template.cells.items()
                 if int((angle(cell) + math.pi) * 3 / math.pi) % 6 == sector]
        assert sum(plot.ground not in {"llanura", "desierto", "playa", "tundra"}
                   for plot in plots) / len(plots) >= 1 / 3


def test_a_generated_map_reads_as_one_country() -> None:
    template = generate(271, 2, random.Random(3))
    assert _mass(template.cells, {"lago"}) >= 6
    assert _mass(template.cells, {"rio"}) >= 6
    assert _mass(template.cells, {"bosque", "bosque_profundo"}) >= 8
    assert _mass(template.cells, {"montana", "montana_rocosa"}) >= 5
    left, right = template.anchors
    assert distance(left, right) >= 13
    assert rotate(left, 3) == right


def test_three_players_turn_the_same_portion() -> None:
    template = generate(271, 3, random.Random(4))
    first, second, third = template.anchors
    assert rotate(first, 2) == second
    assert rotate(second, 2) == third


def test_four_players_keep_a_frontier_between_their_disks() -> None:
    template = generate(547, 4, random.Random(5))
    board = set(template.cells)
    claimed: set[Hex] = set()
    for fort in template.anchors:
        home = owned(fort, 3, board, count=template.home_size)
        assert len(home) == 38
        assert claimed.isdisjoint(home)
        claimed.update(home)
        assert passable(template.cells[fort])
    assert len(claimed) < len(board)


def test_a_plain_march_between_forts_takes_at_least_five_turns() -> None:
    for size, seats in (
        (271, 2), (271, 3), (397, 2), (397, 4), (547, 2), (547, 4),
    ):
        for seed in range(4):
            template = generate(size, seats, random.Random(seed))
            apart = min(
                distance(left, right)
                for left in template.anchors
                for right in template.anchors
                if left != right
            )
            assert apart >= 13
            for left in template.anchors:
                for right in template.anchors:
                    if left != right:
                        assert _turns(template.cells, left, right) >= 5


def test_the_old_disk_is_not_a_generated_terrain_map() -> None:
    with pytest.raises(DomainError):
        generate(19, 2, random.Random(1))
    with pytest.raises(DomainError):
        generate(271, 4, random.Random(1))
    with pytest.raises(DomainError):
        generate(400, 4, random.Random(1))


def test_a_drawn_map_may_keep_only_a_subset_of_the_disk() -> None:
    from hexcampaign.domain.map_document import drawn

    board = list(disk(271))[:40]
    cells = [
        {"q": cell.q, "r": cell.r, "ground": "llanura", "road": False, "bridge": False}
        for cell in board
    ]
    fort = board[0]
    other = board[10]
    template = drawn(
        271,
        cells,
        [{"q": fort.q, "r": fort.r}, {"q": other.q, "r": other.r}],
    )
    assert len(template.cells) == 40
    assert template.seats == 2
    assert not template.generated
    game = create_game("Isla", _table(map_size=271, seats=2), "ana", "Ana")
    lay(game, template, surveyor=None)
    assert set(game.hexes) == set(board)
    assert len(game.plots) == 40


def test_a_drawn_map_rejects_a_lone_fortress_or_cells_outside_the_disk() -> None:
    from hexcampaign.domain.map_document import drawn

    cells = [
        {"q": cell.q, "r": cell.r, "ground": "llanura", "road": False, "bridge": False}
        for cell in list(disk(271))[:12]
    ]
    with pytest.raises(DomainError):
        drawn(271, cells, [{"q": cells[0]["q"], "r": cells[0]["r"]}])
    with pytest.raises(DomainError):
        drawn(
            271,
            cells + [{"q": 60, "r": 0, "ground": "llanura", "road": False, "bridge": False}],
            [],
        )


@pytest.mark.parametrize(("size", "count"), [(271, 19), (397, 28), (547, 38)])
def test_the_copy_starts_each_player_on_their_own_disk(size: int, count: int) -> None:
    game = create_game("Norte", _table(map_size=size), "ana", "Ana")
    original = generate(size, 2, random.Random(1))
    template = load_template(dump_template(original))
    lay(game, template, surveyor=None)
    game = from_dict(to_dict(game))
    accept_seat(game, "boa", "Boa")
    begin(_ready_table(game), "ana", [], NOW)
    board = set(game.hexes)
    forts = {fort.player_id: fort.at() for fort in game.fortresses}
    assert game.discovered["ana"] == owned(forts["ana"], HOME_RADIUS[size], board, count=count)
    assert len(game.discovered["ana"]) == count
    assert forts["boa"] not in game.discovered["ana"]
    view = project(game, "ana", NOW)
    hidden = [cell for cell in view["hexes"] if not cell["known"]]
    assert hidden
    assert "ground" not in hidden[0]
    assert any(item["code"] == "home_land" for item in view["notices"])


def test_old_map_and_campaign_documents_keep_their_original_territory() -> None:
    original = Template(
        397, 2, True, {cell: Plot("llanura") for cell in disk(397)},
        (Hex(9, 0), Hex(-9, 0)),
    )
    saved = dump_template(original)
    saved.pop("home_size")
    game = create_game("Anterior", _table(map_size=397), "ana", "Ana")
    lay(game, load_template(saved), surveyor=None)
    stored = to_dict(game)
    stored.pop("home_size")
    game = from_dict(stored)
    accept_seat(game, "boa", "Boa")
    begin(_ready_table(game), "ana", [], NOW)
    assert game.home_size is None
    assert len(game.discovered["ana"]) == 19


def test_preparation_lets_each_player_lay_roads_from_their_fortress() -> None:
    from hexcampaign.domain.roads import clear_road, finish_roads, place_road, road_budget

    game = create_game("Norte", _table(map_size=271, visibility="total"), "ana", "Ana")
    lay(game, generate(271, 2, random.Random(2)), surveyor="ana")
    accept_seat(game, "boa", "Boa")
    begin(_ready_table(game), "ana", [], NOW)
    assert game.fort_open is True
    _leave_forts(game)
    assert game.phase == "preparing"
    fort = next(item.at() for item in game.fortresses if item.player_id == "ana")
    home = owned(fort, home_radius(271), set(game.hexes), count=game.home_size)
    assert road_budget(game, "ana") == 2 * max(distance(cell, fort) for cell in home)
    first = next(cell for cell in neighbors(fort) if cell in game.plots and passable(game.plots[cell]))
    place_road(game, "ana", first)
    assert game.plots[first].road
    with pytest.raises(DomainError):
        place_road(game, "ana", Hex(0, 0))
    clear_road(game, "ana", first)
    assert not game.plots[first].road
    place_road(game, "ana", first)
    finish_roads(game, "ana", NOW)
    assert "ana" in game.road_ready
    assert game.phase == "preparing"
    assert project(game, "ana", NOW)["prep"] == "armies"
    assert project(game, "boa", NOW)["prep"] == "roads"
    finish_roads(game, "boa", NOW)
    assert game.naming is False
    assert game.phase == "preparing"
    assert project(game, "boa", NOW)["prep"] == "armies"
    _finish_prep(game, NOW)
    assert game.phase == "orders"
    assert game.turn == 1


def test_roads_delta_ships_only_the_changed_hex_and_road_counters() -> None:
    import json

    from hexcampaign.domain.roads import finish_roads, place_road

    game = create_game("Norte", _table(map_size=271, visibility="total"), "ana", "Ana")
    lay(game, generate(271, 2, random.Random(2)), surveyor="ana")
    accept_seat(game, "boa", "Boa")
    begin(_ready_table(game), "ana", [], NOW)
    _leave_forts(game)
    fort = next(item.at() for item in game.fortresses if item.player_id == "ana")
    first = next(cell for cell in neighbors(fort) if cell in game.plots and passable(game.plots[cell]))
    place_road(game, "ana", first)

    full = project(game, "ana", NOW)
    delta = project_roads_delta(game, "ana", [first])
    assert delta["kind"] == "roads_delta"
    assert delta["phase"] == "preparing"
    assert delta["revision"] == game.revision
    assert delta["roads"] == full["roads"]
    assert delta["road_ready"] == full["road_ready"]
    assert len(delta["hexes"]) == 1
    assert delta["hexes"][0]["q"] == first.q
    assert delta["hexes"][0]["r"] == first.r
    assert delta["hexes"][0]["road"] is True
    assert "members" not in delta
    assert "fortresses" not in delta
    assert len(json.dumps(delta, sort_keys=True)) < len(json.dumps(full, sort_keys=True)) // 5

    finish_roads(game, "ana", NOW)
    ready = project_roads_delta(game, "ana", [])
    assert ready["hexes"] == []
    assert ready["roads"]["ready"] is True
    assert "ana" in ready["road_ready"]


def test_fog_binds_owner_and_guest_the_same_way() -> None:
    game = create_game("Norte", _table(map_size=271), "ana", "Ana")
    lay(game, generate(271, 2, random.Random(2)), surveyor="ana")
    accept_seat(game, "boa", "Boa")
    begin(_ready_table(game), "ana", [], NOW)
    _leave_forts(game)
    assert game.phase == "preparing"
    board = set(game.hexes)
    forts = {fort.player_id: fort.at() for fort in game.fortresses}
    assert game.discovered["ana"] == owned(
        forts["ana"], home_radius(271), board, count=game.home_size,
    )
    assert game.discovered["boa"] == owned(
        forts["boa"], home_radius(271), board, count=game.home_size,
    )
    assert len(game.discovered["ana"]) < len(game.hexes)
    assert len(game.discovered["boa"]) < len(game.hexes)


def test_a_road_keeps_paying_for_the_hexes_after_the_eighth() -> None:
    cells = [Hex(index, 0) for index in range(10)]
    plots = {cell: Plot("bosque", road=True) for cell in cells}
    walker = Walker("a", "p", cells[0], cells[1:], budget=1, paid=0)
    moved = walk([walker], plots, set(plots))
    assert moved.positions["a"] == cells[-1]


def test_changing_rules_cannot_detach_the_ground() -> None:
    game = create_game("Norte", _table(map_size=271), "ana", "Ana")
    lay(game, generate(271, 2, random.Random(1)), surveyor=None)
    with pytest.raises(DomainError):
        change_rules(game, "ana", "Norte", _table(map_size=37))
    with pytest.raises(DomainError):
        change_rules(game, "ana", "Norte", _table(visibility="adjacent"))
    change_rules(game, "ana", "Norte", _table(map_size=271, hold_turns=4))
    assert game.plots is not None
    assert len(game.hexes) == 271
    assert game.rules.hold_turns == 4


def test_two_fighting_armies_of_one_player_cannot_lock_the_same_hex() -> None:
    game = create_game("Norte", _table(map_size=271), "ana", "Ana")
    lay(game, generate(271, 2, random.Random(1)), surveyor=None)
    accept_seat(game, "boa", "Boa")
    begin(_ready_table(game), "ana", [], NOW)
    _finish_prep(game)
    fighters = [army for army in game.armies if army.player_id == "ana" and army.kind == "army"]
    scout = next(army for army in game.armies if army.player_id == "ana" and army.kind == "explorer")
    scout.kind = "army"
    own = fighters + [scout]
    fort = next(item for item in game.fortresses if item.player_id == "ana").at()
    assert game.plots is not None
    side = next(cell for cell in neighbors(fort) if exit_cost(game.plots[cell]) == 1)
    target = next(
        cell
        for cell in neighbors(fort)
        if cell != side and distance(cell, side) == 1 and passable(game.plots[cell])
    )
    own[0].q, own[0].r = fort.q, fort.r
    own[1].q, own[1].r = side.q, side.r
    with pytest.raises(DomainError):
        lock_orders(
            game,
            "ana",
            {
                unit.id: ()
                for unit in game.armies
                if unit.player_id == "ana" and not unit.destroyed
            }
            | {own[0].id: (target,), own[1].id: (target,)},
            NOW,
        )


def test_a_seen_fortress_stays_until_the_player_looks_again() -> None:
    game = create_game("Norte", _table(map_size=271), "ana", "Ana")
    lay(game, generate(271, 2, random.Random(1)), surveyor=None)
    accept_seat(game, "boa", "Boa")
    begin(_ready_table(game), "ana", [], NOW)
    fort = next(item for item in game.fortresses if item.player_id == "boa")
    game.discovered["ana"].add(fort.at())
    remember_fort(game, "ana", fort.at())
    game.fortresses = [item for item in game.fortresses if item.player_id != "boa"]
    view = project(game, "ana", NOW)
    assert any(item["player_id"] == "boa" for item in view["fortresses"])


def _mass(cells: dict[Hex, Plot], grounds: set[str]) -> int:
    pending = {cell for cell, plot in cells.items() if plot.ground in grounds}
    best = 0
    while pending:
        start = pending.pop()
        group = {start}
        queue = [start]
        while queue:
            cell = queue.pop()
            for other in neighbors(cell):
                if other in pending:
                    pending.remove(other)
                    group.add(other)
                    queue.append(other)
        best = max(best, len(group))
    return best


def _turns(plots: dict[Hex, Plot], start: Hex, goal: Hex) -> int:
    """Earliest turn a budget of 3 can stand on the goal, counting road refunds."""
    budget = 3
    seen = {(start, budget, 0, 1)}
    queue = [(1, start, budget, 0)]
    while queue:
        turn, cell, left, paid = heapq.heappop(queue)
        if cell == goal:
            return turn
        if turn >= 5:
            continue
        later = (cell, budget, paid, turn + 1)
        if later not in seen:
            seen.add(later)
            heapq.heappush(queue, (turn + 1, cell, budget, paid))
        if left <= 0:
            continue
        cost = exit_cost(plots[cell])
        for nxt in neighbors(cell):
            plot = plots.get(nxt)
            if plot is None or not passable(plot):
                continue
            need = cost - paid
            if left < need:
                carried = (cell, budget, paid + left, turn + 1)
                if carried not in seen:
                    seen.add(carried)
                    heapq.heappush(queue, (turn + 1, cell, budget, paid + left))
                continue
            remain = left - need + (
                1 if plots[cell].road and plots[cell].ground not in {"llanura", "playa", "rio"} else 0
            )
            state = (nxt, remain, 0, turn)
            if state not in seen:
                seen.add(state)
                heapq.heappush(queue, (turn, nxt, remain, 0))
    return 5

