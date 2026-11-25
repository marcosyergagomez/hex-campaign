"""Exit costs, the home disk, and the point clock. No database."""

import pytest

from hexcampaign.domain.clock_march import Walker, walk
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.land import owned, rotate
from hexcampaign.domain.terrain import HOME_RADIUS, Plot, checked_plot, exit_cost, gaze_from


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


def test_leaving_by_a_road_pays_for_one_more_plain() -> None:
    first = Hex(0, 0)
    second = Hex(1, 0)
    third = Hex(2, 0)
    plots = {first: Plot("llanura", road=True), second: Plot("llanura"), third: Plot("llanura")}
    walker = Walker("a", "p", first, [second, third], budget=1, paid=0)
    moved = walk([walker], plots, set(plots))
    assert moved.positions["a"] == third
