"""Choices the owner can still edit until the campaign starts."""

from dataclasses import dataclass

from hexcampaign.domain.errors import DomainError

VISIBILITY = frozenset({"full", "adjacent", "anonymous"})
VICTORY = frozenset({"armies", "fortress", "either"})
PLACEMENT = frozenset({"players", "app"})
MAP_SIZES = frozenset({19, 37, 61})


@dataclass(frozen=True)
class Rules:
    seats: int
    armies: int
    movement: int
    map_size: int
    visibility: str
    victory: str
    hold_turns: int
    placement: str
    order_days: int
    battle_days: int
    missed_turns: int


def rules_from(data: object, *, floor: int = 2) -> Rules:
    """`floor` is 2 for a request. A loaded document may already have fewer seats."""
    if not isinstance(data, dict):
        raise DomainError("rules_invalid")
    try:
        return Rules(
            seats=_span(data["seats"], floor, 4),
            armies=_span(data["armies"], 1, 2),
            movement=_span(data["movement"], 1, 3),
            map_size=_number(data["map_size"], MAP_SIZES),
            visibility=_word(data["visibility"], VISIBILITY),
            victory=_word(data["victory"], VICTORY),
            hold_turns=_span(data["hold_turns"], 1, 999),
            placement=_word(data["placement"], PLACEMENT),
            order_days=_span(data["order_days"], 1, 30),
            battle_days=_span(data["battle_days"], 1, 30),
            missed_turns=_span(data["missed_turns"], 1, 5),
        )
    except (KeyError, TypeError, ValueError):
        raise DomainError("rules_invalid") from None


def campaign_name(value: object) -> str:
    if not isinstance(value, str):
        raise DomainError("rules_invalid")
    name = " ".join(value.split())
    if not name or len(name) > 120:
        raise DomainError("rules_invalid")
    return name


def label(value: object, *, required: bool) -> str:
    if not isinstance(value, str):
        raise DomainError("text_invalid")
    text = " ".join(value.split())
    if len(text) > 40 or (required and not text):
        raise DomainError("text_invalid")
    return text


def roster_text(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2000:
        raise DomainError("text_invalid")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise DomainError("text_invalid")
    return value


def _span(value: object, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    if value < low or value > high:
        raise ValueError
    return value


def _number(value: object, choices: frozenset[int]) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in choices:
        raise ValueError
    return value


def _word(value: object, choices: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError
    return value
