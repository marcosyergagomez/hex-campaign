"""What the table did, kept in order. The players read it when the war is over."""

from hexcampaign.domain.game import Game
from hexcampaign.domain.hexes import Hex

# A finished war is read in full. This only stops a runaway log from rewriting
# a huge document on every order. A normal table does not reach it.
CHRONICLE_LIMIT = 2000


def remember(game: Game, code: str, **detail: object) -> None:
    game.chronicle.append({"turn": game.turn, "code": code, **detail})
    extra = len(game.chronicle) - CHRONICLE_LIMIT
    if extra > 0:
        del game.chronicle[:extra]


def cell(spot: Hex) -> dict[str, int]:
    return {"q": spot.q, "r": spot.r}


def path(steps: tuple[Hex, ...] | list[Hex]) -> list[dict[str, int]]:
    return [cell(step) for step in steps]
