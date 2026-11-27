"""Recruiting, identity, and the button that starts the campaign."""

from dataclasses import replace
from datetime import datetime

from hexcampaign.domain.chronicle import remember
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import (
    Game,
    Member,
    bump,
    find_member,
    notice,
    require_owner,
    require_phase,
    require_player,
    require_staff,
    seated,
)
from hexcampaign.domain.hexes import disk
from hexcampaign.domain.homes import _blank_armies, _deploy, _note_deployment, _open_player_homes
from hexcampaign.domain.identity import checked_color, checked_identity
from hexcampaign.domain.phases import open_first_turn, open_preparation
from hexcampaign.domain.rules import Rules, campaign_description, campaign_name


def create_game(
    name: str,
    rules: Rules,
    owner_id: str,
    alias: str,
    description: object = "",
) -> Game:
    game = Game(
        revision=1,
        name=campaign_name(name),
        phase="recruiting",
        turn=0,
        rules=rules,
        hexes=list(disk(rules.map_size)),
        description=campaign_description(description),
    )
    game.members.append(Member(owner_id, alias, "owner", "active"))
    remember(game, "opened", player_id=owner_id)
    return game


def change_rules(
    game: Game,
    actor: str,
    name: str,
    rules: Rules,
    description: object | None = None,
) -> Game:
    require_owner(game, actor)
    require_phase(game, "recruiting")
    if rules.seats > game.rules.seats or rules.seats < len(seated(game)):
        raise DomainError("rules_invalid")
    if game.plots is not None:
        if rules.map_size != game.rules.map_size:
            raise DomainError("rules_invalid")
        if rules.visibility not in {"total", "charted", "home"}:
            raise DomainError("rules_invalid")
        if game.anchors and rules.seats != len(game.anchors):
            raise DomainError("rules_invalid")
    game.name = campaign_name(name)
    if description is not None:
        game.description = campaign_description(description)
    game.rules = rules
    if game.plots is None:
        game.hexes = list(disk(rules.map_size))
    remember(game, "rules_changed", player_id=actor)
    return bump(game)


def invite_player(game: Game, actor: str, invitee_id: str, alias: str) -> Game:
    require_staff(game, actor)
    require_phase(game, "recruiting")
    if not alias or len(alias) > 24:
        raise DomainError("rules_invalid")
    existing = find_member(game, invitee_id)
    if existing is not None and existing.status == "expelled":
        raise DomainError("expelled")
    if existing is not None and existing.status == "inactive":
        notice(game, "invited", invitee_id, alias=alias)
        remember(game, "invited", player_id=invitee_id)
        return bump(game)
    if existing is not None:
        raise DomainError("already_joined")
    if len(seated(game)) >= game.rules.seats:
        raise DomainError("seat_full")
    notice(game, "invited", invitee_id, alias=alias)
    remember(game, "invited", player_id=invitee_id)
    return bump(game)


def accept_seat(game: Game, player_id: str, alias: str) -> Game:
    require_phase(game, "recruiting")
    if not alias or len(alias) > 24:
        raise DomainError("rules_invalid")
    existing = find_member(game, player_id)
    if existing is not None and existing.status == "expelled":
        raise DomainError("expelled")
    if existing is not None and existing.status == "inactive":
        existing.status = "active"
        existing.cause = ""
        existing.alias = alias
        remember(game, "joined", player_id=player_id)
        return bump(game)
    if existing is not None:
        raise DomainError("already_joined")
    if len(seated(game)) >= game.rules.seats:
        raise DomainError("seat_full")
    game.members.append(Member(player_id, alias, "player", "active"))
    remember(game, "joined", player_id=player_id)
    return bump(game)


def choose_identity(game: Game, actor: str, faction: str, color: str) -> Game:
    member = require_player(game, actor)
    require_phase(game, "recruiting", "placing", "preparing", "orders", "battles")
    if member.status != "active":
        raise DomainError("forbidden")
    if game.phase != "recruiting" and (member.faction or member.color):
        raise DomainError("phase_invalid")
    faction, color = checked_identity(faction, color)
    if any(other.player_id != actor and other.color == color for other in game.members):
        raise DomainError("color_taken")
    member.faction, member.color = faction, color
    # Changing the banner after marking ready puts the seat back in drafting.
    game.lobby_ready.discard(actor)
    return bump(game)


def claim_color(game: Game, actor: str, color: str) -> Game:
    """Reserve a territory colour before the race is chosen. The other seats see it at once."""
    member = require_player(game, actor)
    require_phase(game, "recruiting", "placing", "preparing", "orders", "battles")
    if member.status != "active":
        raise DomainError("forbidden")
    if game.phase != "recruiting" and member.color:
        raise DomainError("phase_invalid")
    color = checked_color(color)
    if any(other.player_id != actor and other.color == color for other in game.members):
        raise DomainError("color_taken")
    if member.color == color:
        return game
    member.color = color
    game.lobby_ready.discard(actor)
    return bump(game)


def mark_ready(game: Game, actor: str) -> Game:
    """Player locks their seat for kickoff after choosing race and colour."""
    require_phase(game, "recruiting")
    member = require_player(game, actor)
    if member.status != "active":
        raise DomainError("forbidden")
    if game.identity_required and (not member.faction or not member.color):
        raise DomainError("identity_required")
    if actor in game.lobby_ready:
        return game
    game.lobby_ready.add(actor)
    remember(game, "lobby_ready", player_id=actor)
    return bump(game)


def clear_ready(game: Game, actor: str) -> Game:
    """Unchecking ready puts the seat back in drafting. The banner stays."""
    require_phase(game, "recruiting")
    member = require_player(game, actor)
    if member.status != "active":
        raise DomainError("forbidden")
    if actor not in game.lobby_ready:
        return game
    game.lobby_ready.discard(actor)
    return bump(game)


def begin(game: Game, actor: str, admin_ids: list[str], now: datetime) -> Game:
    require_owner(game, actor)
    require_phase(game, "recruiting")
    playing = seated(game)
    if len(playing) < 2 or len(playing) != game.rules.seats:
        raise DomainError("phase_invalid")
    active = [member for member in playing if member.status == "active"]
    if game.identity_required and any(not member.faction or not member.color for member in active):
        raise DomainError("identity_required")
    waiting = {member.player_id for member in active}
    if not waiting or not waiting <= game.lobby_ready:
        raise DomainError("lobby_not_ready")
    known = {member.player_id for member in playing}
    if any(player_id not in known for player_id in admin_ids):
        raise DomainError("forbidden")
    for member in playing:
        if member.player_id in admin_ids and member.role != "owner":
            member.role = "admin"
    game.lobby_ready = set()
    remember(game, "started", player_id=actor, placement=game.rules.placement)
    if game.rules.placement == "app":
        _deploy(game)
        _note_deployment(game)
        if game.plots is not None:
            open_preparation(game)
            game.fort_open = True
        else:
            open_first_turn(game, now)
    else:
        _blank_armies(game)
        if game.plots is not None:
            _open_player_homes(game)
            open_preparation(game)
            game.fort_open = True
        else:
            game.phase = "placing"
    return bump(game)

def drop_seat_count(game: Game) -> None:
    """An expulsion before the start removes that chair instead of offering it again."""
    if game.phase != "recruiting":
        return
    living_count = len(seated(game))
    offered = max(game.rules.seats - 1, living_count)
    game.rules = replace(game.rules, seats=offered)
