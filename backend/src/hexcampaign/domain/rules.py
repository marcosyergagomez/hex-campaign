"""Choices the owner can still edit until the campaign starts."""

import unicodedata
from dataclasses import dataclass

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import DISK_RADIUS

VISIBILITY = frozenset({"full", "adjacent", "anonymous", "total", "charted", "home"})
VICTORY = frozenset({"armies", "fortress", "either"})
PLACEMENT = frozenset({"players", "app"})
MAP_SIZES = frozenset(DISK_RADIUS)


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
    roster_required: bool = False


def rules_from(data: object, *, floor: int = 2) -> Rules:
    """`floor` is 2 for a request. A loaded document may already have fewer seats."""
    if not isinstance(data, dict):
        raise DomainError("rules_invalid")
    try:
        return Rules(
            seats=_span(data["seats"], floor, 4),
            armies=_span(data["armies"], 1, 2),
            movement=_span(data["movement"], 1, 5),
            map_size=_number(data["map_size"], MAP_SIZES),
            visibility=_word(data["visibility"], VISIBILITY),
            victory=_word(data["victory"], VICTORY),
            hold_turns=_span(data["hold_turns"], 1, 999),
            placement=_word(data["placement"], PLACEMENT),
            order_days=_span(data["order_days"], 1, 30),
            battle_days=_span(data["battle_days"], 1, 30),
            missed_turns=_span(data["missed_turns"], 1, 5),
            roster_required=_flag(data.get("roster_required", False)),
        )
    except (KeyError, TypeError, ValueError):
        raise DomainError("rules_invalid") from None


DESCRIPTION_LIMIT = 15000


def campaign_name(value: object) -> str:
    return _line(value, limit=120, required=True, code="rules_invalid")


def campaign_description(value: object) -> str:
    """Optional lore blurb; keeps paragraphs, caps length for Warhammer write-ups."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise DomainError("rules_invalid")
    text = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > DESCRIPTION_LIMIT or _hidden(text, allow_breaks=True):
        raise DomainError("rules_invalid")
    return text


def label(value: object, *, required: bool) -> str:
    return _line(value, limit=40, required=required, code="text_invalid")


def roster_text(value: object) -> str:
    if not isinstance(value, str):
        raise DomainError("text_invalid")
    text = unicodedata.normalize("NFKC", value)
    if len(text) > 2000 or _hidden(text, allow_breaks=True):
        raise DomainError("text_invalid")
    return text


def _line(value: object, *, limit: int, required: bool, code: str) -> str:
    if not isinstance(value, str):
        raise DomainError(code)
    text = " ".join(unicodedata.normalize("NFKC", value).split())
    if len(text) > limit or (required and not text) or _hidden(text, allow_breaks=False):
        raise DomainError(code)
    return text


def _hidden(text: str, *, allow_breaks: bool) -> bool:
    for char in text:
        if allow_breaks and char in "\n\t":
            continue
        if unicodedata.category(char) in {"Cc", "Cf"}:
            return True
    return False


def _flag(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError
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
