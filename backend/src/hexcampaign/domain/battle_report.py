"""Players report a battle. Staff judge it when the reports disagree or the clock runs out."""

import random
from datetime import datetime

from hexcampaign.domain.chronicle import remember
from hexcampaign.domain.clock import overdue
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Battle, Game, bump, require_player, require_staff
from hexcampaign.domain.resolution import _settle


def report_battle(
    game: Game,
    actor: str,
    battle_id: str,
    outcome: str,
    now: datetime,
    rng: random.Random | None = None,
) -> Game:
    require_player(game, actor)
    battle = _pending(game, battle_id)
    if overdue(battle.opened_at, game.rules.battle_days, now):
        raise DomainError("phase_invalid")
    if actor not in battle.players:
        raise DomainError("forbidden")
    battle.reports[actor] = _outcome(battle, outcome)
    remember(
        game,
        "battle_reported",
        player_id=actor,
        battle_id=battle.id,
        result=battle.reports[actor],
    )
    _agree(battle)
    _settle(game, now, rng or random.Random())
    return bump(game)


def judge_battle(
    game: Game,
    actor: str,
    battle_id: str,
    outcome: str,
    now: datetime,
    rng: random.Random | None = None,
) -> Game:
    require_staff(game, actor)
    battle = _pending(game, battle_id)
    conflict = len(battle.reports) >= 2 and len(set(battle.reports.values())) > 1
    if not conflict and not overdue(battle.opened_at, game.rules.battle_days, now):
        raise DomainError("phase_invalid")
    battle.result = _outcome(battle, outcome)
    remember(game, "battle_judged", player_id=actor, battle_id=battle.id, result=battle.result)
    _settle(game, now, rng or random.Random())
    return bump(game)

def _pending(game: Game, battle_id: str) -> Battle:
    found = next((battle for battle in game.battles if battle.id == battle_id), None)
    if found is None:
        raise DomainError("battle_unknown")
    if found.reverted or found.result is not None or game.phase != "battles":
        raise DomainError("battle_closed")
    return found


def _outcome(battle: Battle, outcome: str) -> str:
    if outcome == "draw" or outcome in battle.players:
        return outcome
    raise DomainError("battle_unknown")


def _agree(battle: Battle) -> None:
    if any(player_id not in battle.reports for player_id in battle.players):
        return
    values = {battle.reports[player_id] for player_id in battle.players}
    if len(values) == 1:
        battle.result = battle.reports[battle.players[0]]
