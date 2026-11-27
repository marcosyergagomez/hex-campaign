"""Army sheets and the step where a seat stands its tokens."""

from datetime import UTC, datetime

from hexcampaign.domain.chronicle import remember
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game, bump, require_phase, require_player, seated
from hexcampaign.domain.hexes import Hex, deploy_reach, distance
from hexcampaign.domain.homes import _standable, _territory
from hexcampaign.domain.phases import open_first_turn
from hexcampaign.domain.rules import label, roster_text
from hexcampaign.domain.units import is_fighter


def describe_army(
    game: Game,
    actor: str,
    army_id: str,
    name: str,
    commander: str,
    race: str,
    roster: str,
    now: datetime | None = None,
) -> Game:
    """Commander and list are written once this seat has finished its roads."""
    naming_step = _army_step(game, actor)
    bare_table = game.phase == "placing" and game.plots is None
    if not naming_step and not bare_table:
        raise DomainError("phase_invalid")
    found = next((army for army in game.armies if army.id == army_id), None)
    if found is None or found.player_id != actor or found.destroyed:
        raise DomainError("forbidden")
    found.race = label(race, required=False)
    if is_fighter(found):
        commander_text = label(commander, required=True)
        roster_body = roster_text(roster)
        if game.rules.roster_required and not roster_body.strip():
            raise DomainError("sheet_incomplete")
        _reject_duplicate_commander(game, actor, found.id, commander_text)
        found.commander = commander_text
        found.name = commander_text
        found.roster = roster_body
    else:
        found.name = label(name, required=True)
        found.commander = label(commander, required=False)
        found.roster = roster_text(roster)
    remember(game, "named", player_id=actor, army_id=found.id, name=found.name)
    if naming_step:
        _close_seat(game, actor, now)
    return bump(game)


def stand_token(
    game: Game,
    actor: str,
    army_id: str,
    cell: Hex,
    now: datetime | None = None,
) -> Game:
    """During this seat's army step, a piece stands inside the ring around its keep."""
    require_phase(game, "preparing")
    if not _army_step(game, actor):
        raise DomainError("phase_invalid")
    require_player(game, actor)
    army = next((item for item in game.armies if item.id == army_id), None)
    if army is None or army.player_id != actor or army.destroyed:
        raise DomainError("forbidden")
    fort = next((item.at() for item in game.fortresses if item.player_id == actor), None)
    if fort is None:
        raise DomainError("phase_invalid")
    board = set(game.hexes)
    reach = deploy_reach(game.rules.map_size)
    allowed = {cell for cell in board if distance(cell, fort) <= reach}
    if game.plots is not None:
        allowed = {spot for spot in allowed if _standable(game, spot)}
    if cell not in allowed:
        raise DomainError("order_illegal")
    if is_fighter(army):
        for other in game.armies:
            if (
                other.id == army.id
                or other.player_id != actor
                or other.destroyed
                or not is_fighter(other)
            ):
                continue
            if other.at() == cell:
                raise DomainError("order_illegal")
    army.q = cell.q
    army.r = cell.r
    _close_seat(game, actor, now)
    return bump(game)


def settle_preparation(game: Game, now: datetime) -> None:
    """Close the fort stage or the match once every active seat has reached that point."""
    if game.phase != "preparing" or game.plots is None:
        return
    active = {member.player_id for member in seated(game) if member.status == "active"}
    if game.fort_open and active and active <= game.lobby_ready:
        game.fort_open = False
        _territory(game)
    if active and active <= game.prep_done:
        game.naming = False
        game.fort_open = False
        _territory(game)
        open_first_turn(game, now)
        remember(game, "preparation_closed")


def _army_step(game: Game, actor: str) -> bool:
    """True while this seat may still stand tokens and write its sheets."""
    if game.phase != "preparing" or actor in game.prep_done:
        return False
    return game.naming or actor in game.road_ready


def _close_seat(game: Game, actor: str, now: datetime | None) -> None:
    if actor in game.prep_done or not _seat_ready(game, actor):
        return
    game.prep_done.add(actor)
    settle_preparation(game, now or datetime.now(UTC))


def _seat_ready(game: Game, actor: str) -> bool:
    standing = [
        army for army in game.armies
        if army.player_id == actor and not army.destroyed
    ]
    if any(army.at() is None for army in standing):
        return False
    return army_sheets_ready(game, actor)


def army_sheets_ready(game: Game, actor: str) -> bool:
    """True when every living army of this seat has a unique commander and, if required, a list."""
    names: list[str] = []
    for army in game.armies:
        if army.player_id != actor or army.destroyed or not is_fighter(army):
            continue
        if not army.commander.strip():
            return False
        if game.rules.roster_required and not army.roster.strip():
            return False
        names.append(army.commander.casefold())
    return len(names) == len(set(names))


def _reject_duplicate_commander(game: Game, actor: str, army_id: str, commander: str) -> None:
    folded = commander.casefold()
    for army in game.armies:
        if army.id == army_id or army.player_id != actor or army.destroyed or not is_fighter(army):
            continue
        if army.commander.casefold() == folded:
            raise DomainError("commander_taken")

