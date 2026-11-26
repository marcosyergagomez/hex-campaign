"""Movement, fog, victory, expulsion and revert. No database."""

import json
import random
from datetime import UTC, datetime, timedelta

import pytest

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import find_member, from_dict, to_dict
from hexcampaign.domain.hexes import Hex, disk, distance, neighbors
from hexcampaign.domain.identity import COLORS
from hexcampaign.domain.lobby import (
    accept_seat,
    begin,
    choose_identity,
    close_placement,
    create_game,
    invite_player,
    mark_ready,
    place_armies,
)
from hexcampaign.domain.march import march
from hexcampaign.domain.rules import campaign_description, campaign_name, roster_text, rules_from
from hexcampaign.domain.sight import known_hex
from hexcampaign.domain.terrain import Plot
from hexcampaign.domain.turn import (
    close_orders,
    deactivate_player,
    expel_player,
    lock_orders,
    report_battle,
    revert_turn,
)
from hexcampaign.domain.view import project

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_player_identity_is_persisted_and_required_before_a_new_campaign_starts() -> None:
    game = create_game("Estandartes", rules_from(_rules()), "1", "ana")
    game.identity_required = True
    accept_seat(game, "2", "boa")
    choose_identity(game, "1", "cathay", COLORS["garnet"])
    with pytest.raises(DomainError, match="identity_required"):
        begin(game, "1", [], NOW)
    assert game.phase == "recruiting"
    choose_identity(game, "2", "cathay", COLORS["azure"])
    restored = from_dict(to_dict(game))
    assert [(member.faction, member.color) for member in restored.members] == [
        ("cathay", COLORS["garnet"]), ("cathay", COLORS["azure"]),
    ]
    with pytest.raises(DomainError, match="lobby_not_ready"):
        begin(restored, "1", [], NOW)
    mark_ready(restored, "1")
    mark_ready(restored, "2")
    begin(restored, "1", [], NOW)
    assert restored.rules == game.rules
    assert restored.phase == "orders"
    with pytest.raises(DomainError, match="phase_invalid"):
        choose_identity(restored, "1", "empire", COLORS["emerald"])


@pytest.mark.parametrize(("actor", "faction", "color", "error"), [
    ("2", "not_a_faction", COLORS["azure"], "faction_invalid"),
    ("2", "skaven", "red", "color_invalid"),
    ("2", "skaven", COLORS["garnet"], "color_taken"),
    ("outsider", "skaven", COLORS["azure"], "forbidden"),
])
def test_invalid_identity_cannot_mutate_a_campaign(actor, faction, color, error) -> None:
    game = create_game("Estandartes", rules_from(_rules()), "1", "ana")
    accept_seat(game, "2", "boa")
    choose_identity(game, "1", "empire", COLORS["garnet"])
    before = to_dict(game)
    with pytest.raises(DomainError, match=error):
        choose_identity(game, actor, faction, color)
    assert to_dict(game) == before


def test_a_legacy_running_campaign_can_choose_its_banners_once_without_losing_state() -> None:
    old = to_dict(_opened())
    old.pop("identity_required")
    for member in old["members"]:
        member.pop("faction")
        member.pop("color")
    game = from_dict(old)
    armies = to_dict(game)["armies"]
    choose_identity(game, "1", "vampire_counts", COLORS["violet"])
    assert game.turn == old["turn"]
    assert to_dict(game)["armies"] == armies
    assert from_dict(to_dict(game)).members[0].faction == "vampire_counts"
    with pytest.raises(DomainError, match="phase_invalid"):
        choose_identity(game, "1", "skaven", COLORS["garnet"])


def _rules(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "seats": 2,
        "armies": 1,
        "movement": 1,
        "map_size": 19,
        "visibility": "full",
        "victory": "armies",
        "hold_turns": 3,
        "placement": "app",
        "order_days": 7,
        "battle_days": 7,
        "missed_turns": 2,
    }
    data.update(overrides)
    return data


def _ready_table(game):
    for member in game.members:
        if member.status == "active":
            mark_ready(game, member.player_id)
    return game


def _opened(**overrides: object):
    game = create_game("Norte", rules_from(_rules(**overrides)), "1", "ana")
    game = accept_seat(game, "2", "boa")
    return begin(_ready_table(game), "1", [], NOW)


def _army(game, player_id: str, *, living: bool = True):
    return next(
        army
        for army in game.armies
        if army.player_id == player_id
        and army.kind == "army"
        and (not living or not army.destroyed)
    )


def _explorer(game, player_id: str):
    return next(
        army
        for army in game.armies
        if army.player_id == player_id and army.kind == "explorer" and not army.destroyed
    )


def _stay(game, player_id: str) -> dict[str, list]:
    return {
        army.id: []
        for army in game.armies
        if army.player_id == player_id and not army.destroyed
    }


def _orders(game, player_id: str, paths: dict[str, list] | None = None) -> dict[str, list]:
    body = _stay(game, player_id)
    if paths:
        body.update(paths)
    return body


def test_the_chronicle_hides_a_march_until_the_campaign_ends() -> None:
    game = _opened()
    left = _army(game, "1")
    origin = {"q": left.q, "r": left.r}
    step = next(cell for cell in neighbors(left.at()) if cell in set(game.hexes))
    game = lock_orders(game, "1", _orders(game, "1", {left.id: [step]}), NOW)
    game = lock_orders(game, "2", _stay(game, "2"), NOW)

    marched = [
        item
        for item in game.chronicle
        if item["code"] == "marched" and item["army_id"] == left.id
    ]
    assert marched[-1]["origin"] == origin
    assert marched[-1]["destination"] == {"q": step.q, "r": step.r}
    assert project(game, "1", NOW)["chronicle"] == []

    game = revert_turn(game, "1")
    assert any(item["code"] == "reverted" for item in game.chronicle)
    assert any(item["code"] == "marched" and item["army_id"] == left.id for item in game.chronicle)

    game = expel_player(game, "1", "2", random.Random(1), NOW)
    assert game.phase == "finished"
    shown = project(game, "1", NOW)["chronicle"]
    assert any(item["code"] == "marched" for item in shown)
    assert any(item["code"] == "expelled" for item in shown)
    assert any(item["code"] == "finished" for item in shown)
    assert project(game, "outsider", NOW)["chronicle"] == []


def test_disk_sizes_match_the_three_maps() -> None:
    assert len(disk(19)) == 19
    assert len(disk(37)) == 37
    assert len(disk(61)) == 61
    assert distance(Hex(0, 0), Hex(2, -1)) == 2


def test_document_round_trip_keeps_the_revision() -> None:
    game = _opened()

    assert from_dict(to_dict(game)).revision == game.revision
    assert to_dict(from_dict(to_dict(game))) == to_dict(game)


def test_two_fighting_armies_of_one_player_cannot_close_on_the_same_hex() -> None:
    game = _opened()
    first = _army(game, "1")
    second = _explorer(game, "1")
    second.kind = "army"
    shared = next(cell for cell in neighbors(first.at()) if cell != second.at())

    with pytest.raises(DomainError) as caught:
        lock_orders(game, "1", _orders(game, "1", {first.id: [shared], second.id: [shared]}), NOW)

    assert caught.value.code == "order_illegal"


def test_explorer_may_share_a_hex_with_the_army() -> None:
    game = _opened()
    army = _army(game, "1")
    explorer = _explorer(game, "1")
    shared = next(cell for cell in neighbors(army.at()) if cell != explorer.at() and cell in set(game.hexes))
    lock_orders(game, "1", _orders(game, "1", {army.id: [shared], explorer.id: [shared]}), NOW)
    assert game.orders["1"][army.id] == (shared,)
    assert game.orders["1"][explorer.id] == (shared,)


def test_a_visible_enemy_stops_the_path_but_can_be_the_last_hex() -> None:
    game = _opened()
    enemy = _army(game, "2")
    goal = enemy.at()
    approach = next(cell for cell in neighbors(goal) if cell in set(game.hexes))
    beyond = next(cell for cell in neighbors(goal) if cell != approach and cell in set(game.hexes))
    attacker = _army(game, "1")
    attacker.q, attacker.r = approach.q, approach.r

    with pytest.raises(DomainError):
        lock_orders(game, "1", _orders(game, "1", {attacker.id: [goal, beyond]}), NOW)

    locked = lock_orders(game, "1", _orders(game, "1", {attacker.id: [goal]}), NOW)
    assert locked.orders["1"][attacker.id] == (goal,)


def test_the_shorter_path_arrives_first_and_is_not_overtaken() -> None:
    moved = march(
        {"a": Hex(0, 0), "b": Hex(3, 0)},
        {"a": (Hex(1, 0),), "b": (Hex(2, 0), Hex(1, 0))},
        {"a": "1", "b": "2"},
    )

    assert moved.positions["a"] == Hex(1, 0)
    assert moved.positions["b"] == Hex(2, 0)
    assert moved.contacts == ()


def test_enemies_that_swap_hexes_fight_and_friends_pass() -> None:
    enemies = march(
        {"a": Hex(0, 0), "b": Hex(1, 0)},
        {"a": (Hex(1, 0),), "b": (Hex(0, 0),)},
        {"a": "1", "b": "2"},
    )
    friends = march(
        {"a": Hex(0, 0), "b": Hex(1, 0)},
        {"a": (Hex(1, 0),), "b": (Hex(0, 0),)},
        {"a": "1", "b": "1"},
    )

    assert [contact.army_ids for contact in enemies.contacts] == [("a", "b")]
    assert friends.contacts == ()
    assert friends.positions["a"] == Hex(1, 0)
    assert friends.positions["b"] == Hex(0, 0)


def test_a_hidden_army_does_not_block_the_order_and_still_stops_the_move() -> None:
    game = _opened(visibility="anonymous")
    enemy = _army(game, "2")
    attacker = _army(game, "1")
    goal = enemy.at()
    approach = next(cell for cell in neighbors(goal) if cell in set(game.hexes))
    attacker.q, attacker.r = approach.q, approach.r
    game.discovered["1"] = {Hex(attacker.q, attacker.r)}

    game = lock_orders(game, "1", _orders(game, "1", {attacker.id: [goal]}), NOW)
    game = lock_orders(game, "2", _stay(game, "2"), NOW)

    assert game.phase == "battles"
    assert (attacker.q, attacker.r) == (goal.q, goal.r)
    view = project(game, "1", NOW)
    token = next(army for army in view["armies"] if army["id"] == enemy.id)
    assert token["anonymous"] is True
    assert "name" not in token


def test_rival_view_omits_the_secret_order() -> None:
    game = _opened()
    attacker = _army(game, "1")
    dest = next(cell for cell in neighbors(attacker.at()) if cell in set(game.hexes))
    game = lock_orders(game, "1", _orders(game, "1", {attacker.id: [dest]}), NOW)

    rival = project(game, "2", NOW)

    assert rival["orders"] == {}
    assert attacker.id not in json.dumps(rival["orders"])


def test_winner_destroys_the_army_and_a_draw_destroys_none() -> None:
    game = _opened()
    left = _army(game, "1")
    right = _army(game, "2")
    right.q, right.r = 1, 0
    left.q, left.r = 0, 0
    game = lock_orders(game, "1", _orders(game, "1", {left.id: [Hex(1, 0)]}), NOW)
    game = lock_orders(game, "2", _orders(game, "2", {right.id: [Hex(0, 0)]}), NOW)
    battle = game.battles[-1]
    saved = from_dict(to_dict(game))

    agreed = report_battle(game, "1", battle.id, "1", NOW)
    agreed = report_battle(agreed, "2", battle.id, "1", NOW)

    assert agreed.phase == "finished"
    assert agreed.winners == ["1"]
    assert _army(agreed, "2", living=False).destroyed is True

    drawn = report_battle(saved, "1", battle.id, "draw", NOW)
    drawn = report_battle(drawn, "2", battle.id, "draw", NOW)
    assert drawn.phase == "orders"
    assert _army(drawn, "2", living=False).destroyed is False


def test_holding_the_fortress_wins_when_both_conditions_finish_together() -> None:
    game = _opened(victory="either", hold_turns=1)
    fort = next(item for item in game.fortresses if item.player_id == "2")
    attacker = _army(game, "1")
    defender = _army(game, "2")
    step = next(cell for cell in neighbors(fort.at()) if cell in set(game.hexes))
    attacker.q, attacker.r = step.q, step.r
    game = lock_orders(game, "1", _orders(game, "1", {attacker.id: [fort.at()]}), NOW)
    game = lock_orders(game, "2", _orders(game, "2", {defender.id: []}), NOW)
    battle = game.battles[-1]
    game = report_battle(game, "1", battle.id, "1", NOW)
    game = report_battle(game, "2", battle.id, "1", NOW)

    assert game.phase == "finished"
    assert game.winners == ["1"]
    assert next(item for item in game.fortresses if item.player_id == "2").hold == 1


def test_a_missed_order_makes_the_seat_inactive_when_the_admin_closes() -> None:
    game = _opened(missed_turns=1)
    game = lock_orders(game, "1", _stay(game, "1"), NOW)
    game = close_orders(game, "1", NOW)

    missed = find_member(game, "2")
    assert missed is not None
    assert missed.status == "inactive"
    assert missed.cause == "missed"
    assert find_member(game, "1").status == "active"


def test_expulsion_deletes_the_armies_and_refuses_a_return() -> None:
    game = create_game("Norte", rules_from(_rules()), "1", "ana")
    game = accept_seat(game, "2", "boa")
    game = expel_player(game, "1", "2", random.Random(0), NOW)

    with pytest.raises(DomainError) as caught:
        accept_seat(game, "2", "boa")

    assert caught.value.code == "expelled"
    assert game.armies == []
    assert find_member(game, "2").status == "expelled"


def test_revert_restores_the_order_and_marks_the_battle_undone() -> None:
    game = _opened()
    left = _army(game, "1")
    right = _army(game, "2")
    right.q, right.r = 1, 0
    left.q, left.r = 0, 0
    game = lock_orders(game, "1", _orders(game, "1", {left.id: [Hex(1, 0)]}), NOW)
    game = lock_orders(game, "2", _orders(game, "2", {right.id: [Hex(0, 0)]}), NOW)
    battle_id = game.battles[-1].id

    restored = revert_turn(game, "1")

    assert restored.phase == "orders"
    assert restored.turn == 1
    assert _army(restored, "1").at() == Hex(0, 0)
    assert next(battle for battle in restored.battles if battle.id == battle_id).reverted is True
    rival = project(restored, "2", NOW)
    assert left.id not in rival["orders"]
    assert project(restored, "1", NOW)["orders"][left.id] == [{"q": 1, "r": 0}]
    assert any(event["code"] == "reverted" for event in restored.events)


def test_closing_the_account_stays_inactive_when_the_turn_is_reverted() -> None:
    game = _opened()
    game = lock_orders(game, "1", _stay(game, "1"), NOW)
    game = lock_orders(game, "2", _stay(game, "2"), NOW)
    game = deactivate_player(game, "2", random.Random(0))

    restored = revert_turn(game, "1")

    seat = find_member(restored, "2")
    assert seat is not None
    assert seat.status == "inactive"
    assert seat.cause == "account"
    assert find_member(restored, "1").role == "owner"


def test_the_owner_passes_to_the_other_player_when_the_account_closes() -> None:
    game = _opened()
    game = deactivate_player(game, "1", random.Random(0))

    assert find_member(game, "1").status == "inactive"
    assert find_member(game, "1").role == "player"
    assert find_member(game, "2").role == "owner"


def test_an_active_owner_cannot_be_expelled() -> None:
    game = _opened()

    with pytest.raises(DomainError) as caught:
        expel_player(game, "1", "1", random.Random(0), NOW)

    assert caught.value.code == "cannot_expel_owner"


def test_an_army_enters_a_hex_an_enemy_leaves_on_the_same_step() -> None:
    moved = march(
        {"a": Hex(0, 0), "b": Hex(1, 0)},
        {"a": (Hex(1, 0),), "b": (Hex(2, 0),)},
        {"a": "1", "b": "2"},
    )

    assert moved.positions["a"] == Hex(1, 0)
    assert moved.positions["b"] == Hex(2, 0)
    assert moved.contacts == ()


def test_a_missed_owner_hands_the_table_over_and_revert_gives_it_back() -> None:
    game = _opened(missed_turns=1)
    game = lock_orders(game, "2", _stay(game, "2"), NOW)
    game = close_orders(game, "1", NOW, random.Random(0))

    former = find_member(game, "1")
    assert former is not None
    assert former.status == "inactive"
    assert former.role == "player"
    assert find_member(game, "2").role == "owner"

    restored = revert_turn(game, "2")
    assert find_member(restored, "1").status == "active"
    assert find_member(restored, "1").role == "owner"
    assert find_member(restored, "2").role == "player"


def test_an_eliminated_owner_passes_the_table_when_the_war_continues() -> None:
    game = create_game("Norte", rules_from(_rules(seats=3, victory="fortress")), "1", "ana")
    game = accept_seat(game, "2", "boa")
    game = accept_seat(game, "3", "cio")
    game = begin(_ready_table(game), "1", [], NOW)
    owner = _army(game, "1")
    rival = _army(game, "2")
    third = _army(game, "3")
    owner.q, owner.r = 0, 0
    rival.q, rival.r = 1, 0
    third.q, third.r = 2, 0
    game = lock_orders(game, "1", _orders(game, "1", {owner.id: [Hex(1, 0)]}), NOW)
    game = lock_orders(game, "2", _stay(game, "2"), NOW)
    game = lock_orders(game, "3", _stay(game, "3"), NOW)
    battle = game.battles[-1]
    game = report_battle(game, "1", battle.id, "2", NOW)
    game = report_battle(game, "2", battle.id, "2", NOW, random.Random(0))

    assert find_member(game, "1").status == "eliminated"
    assert find_member(game, "1").role == "player"
    assert game.phase == "orders"
    assert find_member(game, random.Random(0).choice(["2", "3"])).role == "owner"


def test_a_hidden_battle_and_its_occupier_stay_out_of_the_other_view() -> None:
    game = create_game("Norte", rules_from(_rules(seats=3, visibility="anonymous")), "1", "ana")
    game = accept_seat(game, "2", "boa")
    game = accept_seat(game, "3", "cio")
    game = begin(_ready_table(game), "1", [], NOW)
    left = _army(game, "1")
    right = _army(game, "2")
    bystander = _army(game, "3")
    left.q, left.r = 0, 0
    right.q, right.r = 1, 0
    bystander.q, bystander.r = 2, -2
    game = lock_orders(game, "1", _orders(game, "1", {left.id: [Hex(1, 0)]}), NOW)
    game = lock_orders(game, "2", _stay(game, "2"), NOW)
    game = lock_orders(game, "3", _stay(game, "3"), NOW)
    game.discovered["3"] = set()
    occupied = next(fort for fort in game.fortresses if fort.player_id == "2")
    occupied.holder_id = "1"
    occupied.hold = 2
    game.discovered["3"].add(occupied.at())

    hidden = project(game, "3", NOW)
    fighter = project(game, "1", NOW)

    assert hidden["battles"] == []
    assert all(fort["holder_id"] is None for fort in hidden["fortresses"])
    assert fighter["battles"]
    assert fighter["battles"][0]["players"] == ["1", "2"]


def test_an_adjacent_holder_is_hidden_until_that_army_is_visible() -> None:
    game = create_game("Norte", rules_from(_rules(seats=3, visibility="adjacent")), "1", "ana")
    game = accept_seat(game, "2", "boa")
    game = accept_seat(game, "3", "cio")
    game = begin(_ready_table(game), "1", [], NOW)
    watcher = _army(game, "3")
    rival = _army(game, "2")
    far = next(
        cell
        for cell in game.hexes
        if cell != watcher.at() and abs(cell.q - watcher.q) + abs(cell.r - watcher.r) > 2
    )
    rival.q, rival.r = far.q, far.r
    fort = next(item for item in game.fortresses if item.player_id == "2")
    fort.q, fort.r = far.q, far.r
    fort.holder_id = "2"
    fort.hold = 2
    game.discovered["3"] = set(game.hexes)

    shown = project(game, "3", NOW)
    seen = next(item for item in shown["fortresses"] if item["q"] == far.q and item["r"] == far.r)

    assert seen["holder_id"] is None
    assert seen["hold"] == 0


def test_a_placed_army_discovers_the_hex_it_stands_on() -> None:
    game = create_game(
        "Norte",
        rules_from(_rules(placement="players", visibility="adjacent")),
        "1",
        "ana",
    )
    game = accept_seat(game, "2", "boa")
    game = begin(_ready_table(game), "1", [], NOW)
    border = [
        cell
        for cell in game.hexes
        if max(abs(cell.q), abs(cell.r), abs(-cell.q - cell.r)) == 2
    ]
    first, second = border[0], border[len(border) // 2]
    own = _army(game, "1")
    scout = _explorer(game, "1")
    other = _army(game, "2")
    other_scout = _explorer(game, "2")
    game = place_armies(game, "1", first, {own.id: Hex(0, 0), scout.id: Hex(0, 0)})
    game = place_armies(game, "2", second, {other.id: Hex(1, 0), other_scout.id: Hex(1, 0)})
    game = close_placement(game, "1", NOW)

    assert known_hex(game, "1", Hex(0, 0))
    assert known_hex(game, "2", Hex(1, 0))


def test_players_place_forts_inside_pre_marked_home_land() -> None:
    game = create_game(
        "Hogares",
        rules_from(_rules(placement="players", visibility="home", map_size=37)),
        "1",
        "ana",
    )
    game = accept_seat(game, "2", "boa")
    game.plots = {cell: Plot("llanura") for cell in game.hexes}
    game.home_size = 7
    game = begin(_ready_table(game), "1", [], NOW)
    assert game.phase == "placing"
    assert len(game.anchors) == 2
    home_one = set(game.discovered["1"])
    home_two = set(game.discovered["2"])
    assert home_one and home_two and home_one.isdisjoint(home_two)
    outsider = next(cell for cell in game.hexes if cell not in home_one)
    own = _army(game, "1")
    scout = _explorer(game, "1")
    home_cell = next(iter(home_one))
    with pytest.raises(DomainError, match="order_illegal"):
        place_armies(game, "1", outsider, {own.id: home_cell, scout.id: home_cell})
    fort = next(iter(home_one))
    army_spot = next(cell for cell in home_one if cell != fort)
    game = place_armies(game, "1", fort, {own.id: army_spot, scout.id: army_spot})
    assert next(item for item in game.fortresses if item.player_id == "1").at() == fort


def test_a_name_rejects_a_null_and_a_hidden_direction_mark() -> None:
    with pytest.raises(DomainError) as nul:
        campaign_name("Norte\x00")
    with pytest.raises(DomainError) as bidi:
        campaign_name("Norte\u202e")

    assert nul.value.code == "rules_invalid"
    assert bidi.value.code == "rules_invalid"
    assert roster_text("a\nb") == "a\nb"
    with pytest.raises(DomainError) as hidden:
        roster_text("a\x00b")
    assert hidden.value.code == "text_invalid"


def test_campaign_description_keeps_paragraphs_and_caps_length() -> None:
    lore = "En el Imperio\n\nhubo una guerra."
    assert campaign_description(lore) == lore
    assert campaign_description(None) == ""
    assert campaign_description("  ") == ""
    with pytest.raises(DomainError) as long:
        campaign_description("x" * 15001)
    assert long.value.code == "rules_invalid"
    game = create_game("Cronica", rules_from(_rules()), "1", "ana", lore)
    assert game.description == lore
    assert from_dict(to_dict(game)).description == lore


def test_orders_are_due_a_full_day_count_after_they_open(now=NOW) -> None:
    game = _opened(order_days=2)
    quiet = project(game, "1", now + timedelta(days=1))
    due = project(game, "1", now + timedelta(days=2))

    assert quiet["orders_due"] is False
    assert due["orders_due"] is True


def test_invite_is_refused_when_every_seat_is_taken() -> None:
    game = create_game("Llena", rules_from(_rules(seats=2)), "1", "ana")
    accept_seat(game, "2", "boa")
    with pytest.raises(DomainError, match="seat_full"):
        invite_player(game, "1", "3", "cio")
