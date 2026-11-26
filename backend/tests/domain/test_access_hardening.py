"""Seat status gates reads and player writes after leave or expulsion."""

from datetime import UTC, datetime

import pytest

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import require_player
from hexcampaign.domain.lobby import accept_seat, begin, create_game, mark_ready
from hexcampaign.domain.rules import rules_from
from hexcampaign.domain.turn import expel_player, lock_orders, withdraw_player

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _rules(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "seats": 2,
        "armies": 1,
        "movement": 1,
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


def _opened():
    game = create_game("Acceso", rules_from(_rules()), "1", "ana")
    accept_seat(game, "2", "boa")
    return begin(_ready(game), "1", [], NOW)


def test_inactive_seat_cannot_lock_orders() -> None:
    game = _opened()
    withdraw_player(game, "2", __import__("random").Random(1), NOW)
    assert next(member for member in game.members if member.player_id == "2").status == "inactive"
    with pytest.raises(DomainError, match="forbidden"):
        require_player(game, "2")
    with pytest.raises(DomainError, match="forbidden"):
        lock_orders(
            game,
            "2",
            {
                army.id: []
                for army in game.armies
                if army.player_id == "2" and not army.destroyed
            },
            NOW,
        )


def test_expelled_seat_cannot_act_as_player() -> None:
    import random

    game = create_game("Acceso", rules_from(_rules(seats=3)), "1", "ana")
    accept_seat(game, "2", "boa")
    accept_seat(game, "3", "cio")
    game = begin(_ready(game), "1", [], NOW)
    expel_player(game, "1", "2", random.Random(1), NOW)
    assert game.phase == "orders"
    with pytest.raises(DomainError, match="forbidden"):
        require_player(game, "2")
    with pytest.raises(DomainError, match="forbidden"):
        lock_orders(
            game,
            "2",
            {
                army.id: []
                for army in game.armies
                if army.player_id == "2" and not army.destroyed
            },
            NOW,
        )
