"""A document saved before schema_version still loads, and nothing in it is dropped."""

import pytest

from apps.campaigns.document import SCHEMA_VERSION, from_dict, to_dict
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.lobby import create_game
from hexcampaign.domain.rules import rules_from

_RULES = {
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


def test_a_document_without_schema_version_migrates_without_losing_fields() -> None:
    game = create_game("Norte", rules_from(_RULES), "1", "ana")
    game.description = "Una marca en el mapa."
    stored = to_dict(game)
    assert stored["schema_version"] == SCHEMA_VERSION
    legacy = dict(stored)
    del legacy["schema_version"]

    restored = from_dict(legacy)

    assert to_dict(restored) == stored


def test_a_future_schema_version_is_rejected() -> None:
    stored = to_dict(create_game("Norte", rules_from(_RULES), "1", "ana"))
    stored["schema_version"] = SCHEMA_VERSION + 1
    with pytest.raises(DomainError) as raised:
        from_dict(stored)
    assert raised.value.code == "rules_invalid"
