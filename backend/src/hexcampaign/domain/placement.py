"""Where each seat plants its fortress before the roads."""

from datetime import datetime

from hexcampaign.domain.chronicle import remember
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import (
    Fortress,
    Game,
    bump,
    require_owner,
    require_phase,
    require_player,
    seated,
)
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.homes import (
    _disks_overlap,
    _frontier,
    _home_notice,
    _note_deployment,
    _park_on_standable,
    _player_home_zone,
    _standable,
    _territory,
)
from hexcampaign.domain.muster import army_sheets_ready, settle_preparation
from hexcampaign.domain.phases import open_first_turn, open_preparation


def place_armies(game: Game, actor: str, fortress: Hex, spots: dict[str, Hex]) -> Game:
    moving_fort = game.phase == "preparing" and game.fort_open
    if game.phase != "placing" and not moving_fort:
        raise DomainError("phase_invalid")
    require_player(game, actor)
    if moving_fort and actor in game.lobby_ready:
        raise DomainError("phase_invalid")
    own = [army for army in game.armies if army.player_id == actor and not army.destroyed]
    board = set(game.hexes)
    if set(spots) != {army.id for army in own}:
        raise DomainError("order_illegal")
    if fortress not in board or any(spot not in board for spot in spots.values()):
        raise DomainError("order_illegal")
    home = _player_home_zone(game, actor) if game.plots is not None else None
    if home is not None and fortress not in home:
        raise DomainError("order_illegal")
    if game.plots is not None and not _standable(game, fortress):
        raise DomainError("order_illegal")
    if game.plots is not None and home is None and _disks_overlap(game, actor, fortress):
        raise DomainError("order_illegal")
    if game.plots is not None:
        # A keep may sit beside a lake or a cliff. Tokens still need passable ground.
        spots = _park_on_standable(game, actor, fortress, spots, home)
    elif home is not None and any(spot not in home for spot in spots.values()):
        raise DomainError("order_illegal")
    fighters = [army for army in own if army.kind == "army"]
    explorers = [army for army in own if army.kind == "explorer"]
    fighter_cells = [spots[army.id] for army in fighters]
    if len(set(fighter_cells)) != len(fighter_cells):
        raise DomainError("order_illegal")
    # The keep is about to leave its old hex, so that cell is no longer a fortress.
    forts = {fortress, *(fort.at() for fort in game.fortresses if fort.player_id != actor)}
    if any(spots[army.id] in forts for army in explorers):
        raise DomainError("order_illegal")
    _reject_overlap(
        game,
        actor,
        fortress,
        {army.id: spots[army.id] for army in fighters},
        {army.id: spots[army.id] for army in explorers},
    )
    current = next((fort for fort in game.fortresses if fort.player_id == actor), None)
    if current is None:
        game.fortresses.append(Fortress(actor, fortress.q, fortress.r))
    else:
        current.q = fortress.q
        current.r = fortress.r
    for army in own:
        army.q = spots[army.id].q
        army.r = spots[army.id].r
    remember(game, "placed", player_id=actor, q=fortress.q, r=fortress.r)
    _note_deployment(game, actor)
    return bump(game)


def close_placement(game: Game, actor: str, now: datetime) -> Game:
    require_owner(game, actor)
    require_phase(game, "placing")
    for member in seated(game):
        if not any(fort.player_id == member.player_id for fort in game.fortresses):
            raise DomainError("phase_invalid")
    if any(army.at() is None for army in game.armies if not army.destroyed):
        raise DomainError("phase_invalid")
    return _open_after_placement(game, actor, now)


def confirm_placement(game: Game, actor: str, now: datetime) -> Game:
    """A seat locks its fortress and goes on to roads. The others keep placing."""
    if game.phase == "preparing" and game.fort_open:
        return _confirm_opened_fort(game, actor, now)
    require_phase(game, "placing")
    member = require_player(game, actor)
    if member.status != "active":
        raise DomainError("forbidden")
    if not any(fort.player_id == actor for fort in game.fortresses):
        raise DomainError("phase_invalid")
    if any(
        army.player_id == actor and not army.destroyed and army.at() is None
        for army in game.armies
    ):
        raise DomainError("phase_invalid")
    if actor in game.lobby_ready:
        return game
    game.lobby_ready.add(actor)
    active = {item.player_id for item in seated(game) if item.status == "active"}
    if not active <= game.lobby_ready:
        return bump(game)
    game.lobby_ready = set()
    return _open_after_placement(game, actor, now)


def _confirm_opened_fort(game: Game, actor: str, now: datetime) -> Game:
    member = require_player(game, actor)
    if member.status != "active":
        raise DomainError("forbidden")
    if not any(fort.player_id == actor for fort in game.fortresses):
        raise DomainError("phase_invalid")
    if actor in game.lobby_ready:
        return game
    game.lobby_ready.add(actor)
    settle_preparation(game, now)
    return bump(game)


def _open_after_placement(game: Game, actor: str, now: datetime) -> Game:
    if game.plots is not None and not _frontier(game):
        raise DomainError("phase_invalid")
    _territory(game)
    _home_notice(game)
    remember(game, "placement_closed", player_id=actor)
    if game.plots is not None:
        open_preparation(game)
    else:
        for member in seated(game):
            if member.status == "active" and not army_sheets_ready(game, member.player_id):
                raise DomainError("sheet_incomplete")
        open_first_turn(game, now)
    return bump(game)


def _reject_overlap(
    game: Game,
    actor: str,
    fortress: Hex,
    fighters: dict[str, Hex],
    explorers: dict[str, Hex],
) -> None:
    cells = {fortress, *fighters.values(), *explorers.values()}
    for fort in game.fortresses:
        if fort.player_id != actor and fort.at() in cells:
            raise DomainError("order_illegal")
    for army in game.armies:
        if army.player_id == actor or army.at() is None:
            continue
        # Fighting armies may not start on an enemy token; explorers may share.
        if army.at() in fighters.values():
            raise DomainError("order_illegal")
