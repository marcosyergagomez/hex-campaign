"""Campaign phase transitions shared by lobby and preparation."""

from datetime import datetime

from hexcampaign.domain.clock import stamp
from hexcampaign.domain.game import Game


def open_preparation(game: Game) -> None:
    game.phase = "preparing"
    game.road_ready = set()


def open_first_turn(game: Game, now: datetime) -> None:
    game.phase = "orders"
    game.turn = 1
    game.orders_opened_at = stamp(now)
