"""Explorer tokens scout farther, never fight, and stay out of forts."""

from datetime import UTC, datetime

from hexcampaign.domain.hexes import Hex, distance, neighbors
from hexcampaign.domain.lobby import accept_seat, begin, create_game, mark_ready
from hexcampaign.domain.rules import rules_from
from hexcampaign.domain.units import EXPLORER_GAZE_BONUS, EXPLORER_MOVE_BONUS, move_budget, unit_gaze
from hexcampaign.domain.view import project

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _rules(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "seats": 2,
        "armies": 1,
        "movement": 3,
        "map_size": 19,
        "visibility": "adjacent",
        "victory": "armies",
        "hold_turns": 3,
        "placement": "app",
        "order_days": 7,
        "battle_days": 7,
        "missed_turns": 2,
    }
    data.update(overrides)
    return data


def _ready(game):
    for member in game.members:
        if member.status == "active":
            mark_ready(game, member.player_id)
    return game


def _opened(**overrides: object):
    game = create_game("Exploradores", rules_from(_rules(**overrides)), "1", "ana")
    accept_seat(game, "2", "boa")
    return begin(_ready(game), "1", [], NOW)


def test_each_seat_deploys_one_army_and_one_explorer() -> None:
    game = _opened()
    for player_id in ("1", "2"):
        kinds = sorted(army.kind for army in game.armies if army.player_id == player_id)
        assert kinds == ["army", "explorer"]
    fort = next(item for item in game.fortresses if item.player_id == "1").at()
    army = next(item for item in game.armies if item.player_id == "1" and item.kind == "army")
    scout = next(item for item in game.armies if item.player_id == "1" and item.kind == "explorer")
    assert army.at() == fort
    assert scout.at() is not None and scout.at() != fort
    assert distance(scout.at(), fort) == 1


def test_explorer_moves_and_sees_farther_than_the_army() -> None:
    game = _opened()
    army = next(item for item in game.armies if item.player_id == "1" and item.kind == "army")
    scout = next(item for item in game.armies if item.player_id == "1" and item.kind == "explorer")
    assert move_budget(game.rules.movement, scout) == game.rules.movement + EXPLORER_MOVE_BONUS
    assert move_budget(game.rules.movement, army) == game.rules.movement
    assert unit_gaze(scout, None) == unit_gaze(army, None) + EXPLORER_GAZE_BONUS


def test_view_exposes_token_kind() -> None:
    game = _opened()
    shown = project(game, "1", NOW)["armies"]
    kinds = {item["kind"] for item in shown if item.get("player_id") == "1"}
    assert kinds == {"army", "explorer"}
