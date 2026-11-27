"""Players leaving the table: expulsion, withdrawal, promotion and the next owner."""

import random
from datetime import datetime

from hexcampaign.domain.chronicle import remember
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import (
    Game,
    Member,
    bump,
    find_member,
    notice,
    require_phase,
    require_staff,
    seated,
)
from hexcampaign.domain.muster import settle_preparation
from hexcampaign.domain.recruit import drop_seat_count
from hexcampaign.domain.resolution import _ready, _resolve, _settle, _winners


def expel_player(game: Game, actor: str, target_id: str, rng: random.Random, now: datetime) -> Game:
    require_staff(game, actor)
    target = find_member(game, target_id)
    if target is None or target.status == "expelled":
        raise DomainError("forbidden")
    if target.role == "owner" and target.status == "active":
        raise DomainError("cannot_expel_owner")
    remember(game, "expelled", player_id=actor, target_id=target.player_id)
    game.lobby_ready.discard(target.player_id)
    _remove(game, target)
    if not _active_staff(game):
        _hand_over(game, rng)
    return _after_exit(game, target.player_id, now, rng)


def leave_campaign(game: Game, actor: str, rng: random.Random, now: datetime) -> Game:
    target = find_member(game, actor)
    if target is None or target.status in {"expelled", "eliminated"}:
        raise DomainError("forbidden")
    was_owner = target.role == "owner"
    remember(game, "left", player_id=actor)
    game.lobby_ready.discard(actor)
    _remove(game, target)
    if was_owner or not _active_staff(game):
        _hand_over(game, rng)
    return _after_exit(game, target.player_id, now, rng)


def promote_player(game: Game, actor: str, target_id: str) -> Game:
    require_staff(game, actor)
    require_phase(game, "placing", "preparing", "orders", "battles", "finished")
    target = find_member(game, target_id)
    if target is None or target.status == "expelled":
        raise DomainError("forbidden")
    if target.role == "player":
        target.role = "admin"
        remember(game, "promoted", player_id=actor, target_id=target.player_id)
    return bump(game)

def deactivate_player(game: Game, player_id: str, rng: random.Random) -> Game:
    member = find_member(game, player_id)
    if member is None or member.status == "expelled":
        return game
    if member.status == "inactive" and member.cause == "account":
        return game
    was_owner = member.role == "owner"
    member.status = "inactive"
    member.cause = "account"
    notice(game, "player_inactive", player_id, cause="account")
    remember(game, "inactive", player_id=player_id, cause="account")
    if was_owner or not _active_staff(game):
        _hand_over(game, rng)
    return bump(game)


def withdraw_player(game: Game, actor: str, rng: random.Random, now: datetime) -> Game:
    """A non-staff player steps away: inactive seat, still restorable by staff."""
    member = find_member(game, actor)
    if member is None or member.status != "active":
        raise DomainError("forbidden")
    if member.role in {"owner", "admin"}:
        raise DomainError("forbidden")
    member.status = "inactive"
    member.cause = "withdrawn"
    game.lobby_ready.discard(actor)
    notice(game, "player_inactive", actor, cause="withdrawn")
    remember(game, "withdrawn", player_id=actor)
    return _after_exit(game, actor, now, rng)


def restore_player(game: Game, actor: str, target_id: str) -> Game:
    """Staff bring an inactive seat back into the match."""
    require_staff(game, actor)
    require_phase(game, "recruiting", "placing", "preparing", "orders", "battles")
    target = find_member(game, target_id)
    if target is None or target.status != "inactive":
        raise DomainError("forbidden")
    target.status = "active"
    target.cause = ""
    remember(game, "restored", player_id=actor, target_id=target.player_id)
    return bump(game)

def _remove(game: Game, member: Member) -> None:
    member.status = "expelled"
    member.role = "player"
    member.cause = ""
    game.armies = [army for army in game.armies if army.player_id != member.player_id]
    game.fortresses = [fort for fort in game.fortresses if fort.player_id != member.player_id]
    game.orders.pop(member.player_id, None)
    game.discovered.pop(member.player_id, None)
    game.fort_memory.pop(member.player_id, None)
    drop_seat_count(game)


def _after_exit(game: Game, player_id: str, now: datetime, rng: random.Random) -> Game:
    _release(game, player_id)
    if game.phase == "battles":
        _settle(game, now, rng)
    elif game.phase == "orders" and _ready(game):
        return _resolve(game, now, set(), rng)
    elif game.phase == "preparing":
        game.road_ready.discard(player_id)
        game.prep_done.discard(player_id)
        settle_preparation(game, now)
    elif _campaign_over(game):
        game.phase = "finished"
        game.winners = _winners(game) or []
        game.orders = {}
        remember(game, "finished", winners=list(game.winners))
    return bump(game)


def _release(game: Game, player_id: str) -> None:
    for battle in game.battles:
        if battle.reverted or battle.result is not None or battle.turn != game.turn:
            continue
        if player_id not in battle.players:
            continue
        others = [other for other in battle.players if other != player_id]
        battle.result = others[0] if len(others) == 1 else "draw"


def _campaign_over(game: Game) -> bool:
    if game.phase in {"recruiting", "placing", "preparing", "finished"}:
        return False
    return len([member for member in seated(game) if member.status != "eliminated"]) <= 1


def _hand_over(game: Game, rng: random.Random) -> None:
    owner = next((member for member in game.members if member.role == "owner"), None)
    pool = [member for member in game.members if member.status == "active"]
    if owner is not None and owner.status != "expelled":
        owner.role = "player"
    if not pool:
        game.phase = "finished"
        game.winners = []
        remember(game, "finished", winners=[])
        return
    chosen = rng.choice(sorted(pool, key=lambda member: member.player_id))
    chosen.role = "owner"
    notice(game, "owner_transferred", chosen.player_id)
    remember(game, "owner_transferred", player_id=chosen.player_id)


def _active_staff(game: Game) -> list[Member]:
    return [
        member
        for member in game.members
        if member.role in {"owner", "admin"} and member.status == "active"
    ]
