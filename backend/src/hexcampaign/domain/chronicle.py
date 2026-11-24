"""What the table did, kept in order. The players read it when the war is over."""

from hexcampaign.domain.game import Game
from hexcampaign.domain.hexes import Hex


def remember(game: Game, code: str, **detail: object) -> None:
    game.chronicle.append({"turn": game.turn, "code": code, **detail})


def cell(spot: Hex) -> dict[str, int]:
    return {"q": spot.q, "r": spot.r}


def path(steps: tuple[Hex, ...] | list[Hex]) -> list[dict[str, int]]:
    return [cell(step) for step in steps]
