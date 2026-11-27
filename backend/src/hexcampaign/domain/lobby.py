"""Recruiting, the start button, and where the armies stand before the first order."""

from dataclasses import replace
from datetime import UTC, datetime

from hexcampaign.domain.chronicle import remember
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import (
    Army,
    Fortress,
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
from hexcampaign.domain.hexes import (
    DISK_RADIUS,
    Hex,
    angle,
    deploy_reach,
    disk,
    distance,
    neighbors,
)
from hexcampaign.domain.identity import checked_color, checked_identity
from hexcampaign.domain.land import home_radius, owned
from hexcampaign.domain.phases import open_first_turn, open_preparation
from hexcampaign.domain.rules import Rules, campaign_description, campaign_name, label, roster_text
from hexcampaign.domain.terrain import passable
from hexcampaign.domain.territory import assigned_homes, home_land
from hexcampaign.domain.units import is_fighter


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


def _open_player_homes(game: Game) -> None:
    """Carve each seat a pre-set home disk; players must place inside it.

    During placing there is no fortress yet, so the home disk is staged in
    `discovered` until close_placement replaces it with real fog-of-war.
    """
    players = seated(game)
    centers = _seat_centers(game, players)
    game.anchors = list(centers)
    board = set(game.hexes)
    radius = home_radius(game.rules.map_size)
    for member, center in zip(players, centers, strict=True):
        zone = owned(center, radius, board, count=game.home_size)
        if center not in zone or not any(_standable(game, cell) for cell in zone):
            raise DomainError("rules_invalid")
        game.discovered[member.player_id] = set(zone)


def _player_home_zone(game: Game, actor: str) -> set[Hex]:
    if game.phase == "placing" or game.fort_open:
        zone = assigned_homes(game).get(actor)
        if zone:
            return set(zone)
    zone = game.discovered.get(actor)
    if zone:
        return set(zone)
    players = seated(game)
    if len(game.anchors) != len(players):
        raise DomainError("rules_invalid")
    index = next(i for i, member in enumerate(players) if member.player_id == actor)
    return owned(
        game.anchors[index],
        home_radius(game.rules.map_size),
        set(game.hexes),
        count=game.home_size,
    )


def _seat_centers(game: Game, players: list[Member]) -> list[Hex]:
    if game.anchors and len(game.anchors) == len(players):
        return list(game.anchors)
    radius = DISK_RADIUS[game.rules.map_size]
    border = [cell for cell in game.hexes if distance(cell, Hex(0, 0)) == radius]
    border.sort(key=lambda cell: (angle(cell), cell.q, cell.r))
    if game.plots is not None:
        border = [cell for cell in border if _standable(game, cell)]
    if not border:
        raise DomainError("rules_invalid")
    return [border[(index * len(border)) // len(players)] for index in range(len(players))]


def _deploy(game: Game) -> None:
    players = seated(game)
    chosen = _seat_centers(game, players)
    game.anchors = list(chosen)
    taken = set(chosen)
    board = _stand_board(game)
    for member, fort in zip(players, chosen, strict=True):
        if game.plots is not None and not _standable(game, fort):
            raise DomainError("rules_invalid")
        game.fortresses.append(Fortress(member.player_id, fort.q, fort.r))
        _seat_tokens(game, member.player_id, member.faction, fort, taken, board)
    _territory(game)
    _home_notice(game)


def _blank_armies(game: Game) -> None:
    for member in seated(game):
        _seat_tokens(game, member.player_id, member.faction, None, set(), set())


def _seat_tokens(
    game: Game,
    player_id: str,
    race: str,
    fort: Hex | None,
    taken: set[Hex],
    board: set[Hex],
) -> None:
    """One explorer, plus as many fighting armies as the table asked for."""
    for index in range(game.rules.armies):
        spot = None
        if fort is not None:
            spot = fort if index == 0 else _beside(fort, taken, board)
            taken.add(spot)
        game.armies.append(_army(game, player_id, str(index + 1), spot, kind="army", race=race))
    explorer_spot = _beside(fort, taken, board) if fort is not None else None
    if explorer_spot is not None:
        taken.add(explorer_spot)
    game.armies.append(
        _army(game, player_id, "Explorador", explorer_spot, kind="explorer", race=race)
    )


def _army(
    game: Game,
    player_id: str,
    name: str,
    spot: Hex | None,
    *,
    kind: str = "army",
    race: str = "",
) -> Army:
    army = Army(
        id=f"a{game.next_id}",
        player_id=player_id,
        name=name,
        commander="",
        race=race,
        roster="",
        q=None if spot is None else spot.q,
        r=None if spot is None else spot.r,
        kind=kind,
    )
    game.next_id += 1
    return army


def _beside(origin: Hex, taken: set[Hex], board: set[Hex]) -> Hex:
    options = [cell for cell in neighbors(origin) if cell in board and cell not in taken]
    options.sort(key=lambda cell: (distance(cell, Hex(0, 0)), cell.q, cell.r))
    if not options:
        raise DomainError("rules_invalid")
    return options[0]


def _note_deployment(game: Game, player_id: str | None = None) -> None:
    armies = [
        army for army in game.armies if player_id is None or army.player_id == player_id
    ]
    for army in armies:
        if army.q is None or army.r is None:
            continue
        remember(
            game,
            "deployed",
            player_id=army.player_id,
            army_id=army.id,
            name=army.name,
            q=army.q,
            r=army.r,
        )


def _territory(game: Game) -> None:
    players = [member.player_id for member in seated(game)]
    if game.plots is not None and game.rules.visibility in {"full", "total", "charted"}:
        for player_id in players:
            game.discovered[player_id] = set(game.hexes)
        return
    if game.plots is not None and game.rules.visibility == "home":
        board = set(game.hexes)
        for player_id in players:
            game.discovered[player_id] = home_land(game, player_id, board=board)
        return
    forts = [(fort.at(), fort.player_id) for fort in game.fortresses]
    if game.rules.visibility == "full":
        for player_id in players:
            game.discovered[player_id] = set(game.hexes)
        return
    for player_id in players:
        game.discovered[player_id] = set()
    for cell in game.hexes:
        best: int | None = None
        owners: list[str] = []
        for fort, player_id in forts:
            span = distance(cell, fort)
            if best is None or span < best:
                best = span
                owners = [player_id]
            elif span == best:
                owners.append(player_id)
        if len(owners) == 1:
            game.discovered[owners[0]].add(cell)
    for army in game.armies:
        spot = army.at()
        if spot is None or army.destroyed:
            continue
        game.discovered.setdefault(army.player_id, set()).add(spot)


def drop_seat_count(game: Game) -> None:
    """An expulsion before the start removes that chair instead of offering it again."""
    if game.phase != "recruiting":
        return
    living_count = len(seated(game))
    offered = max(game.rules.seats - 1, living_count)
    game.rules = replace(game.rules, seats=offered)


def _stand_board(game: Game) -> set[Hex]:
    if game.plots is None:
        return set(game.hexes)
    return {cell for cell in game.hexes if _standable(game, cell)}


def _park_on_standable(
    game: Game,
    actor: str,
    fortress: Hex,
    spots: dict[str, Hex],
    home: set[Hex] | None,
) -> dict[str, Hex]:
    """Move any token that was left on impassable ground onto a passable home hex."""
    zone = set(game.hexes) if home is None else home
    other_forts = {fort.at() for fort in game.fortresses if fort.player_id != actor}
    ordered = sorted(zone, key=lambda cell: (distance(cell, fortress), cell.q, cell.r))
    taken: set[Hex] = set()
    parked: dict[str, Hex] = {}
    own = [army for army in game.armies if army.player_id == actor and not army.destroyed]

    def claim(preferred: Hex | None, *, fighter: bool) -> Hex:
        for cell in ((preferred,) if preferred is not None else ()):
            if _free(cell, fighter=fighter):
                if fighter:
                    taken.add(cell)
                return cell
        for cell in ordered:
            if _free(cell, fighter=fighter):
                if fighter:
                    taken.add(cell)
                return cell
        raise DomainError("order_illegal")

    def _free(cell: Hex, *, fighter: bool) -> bool:
        if cell not in zone or not _standable(game, cell) or cell in other_forts:
            return False
        if fighter and cell in taken:
            return False
        if not fighter and (cell == fortress or cell in taken):
            return False
        return True

    fighters = [army for army in own if army.kind == "army"]
    for index, army in enumerate(fighters):
        preferred = fortress if index == 0 else spots.get(army.id)
        parked[army.id] = claim(preferred, fighter=True)
    for army in own:
        if army.kind != "explorer":
            continue
        parked[army.id] = claim(spots.get(army.id), fighter=False)
    return parked


def _standable(game: Game, cell: Hex) -> bool:
    plot = None if game.plots is None else game.plots.get(cell)
    return plot is not None and passable(plot)


def _disks_overlap(game: Game, actor: str, fortress: Hex) -> bool:
    board = set(game.hexes)
    radius = home_radius(game.rules.map_size)
    claimed = owned(fortress, radius, board, count=game.home_size)
    for fort in game.fortresses:
        if fort.player_id != actor and claimed & owned(
            fort.at(), radius, board, count=game.home_size,
        ):
            return True
    return False


def _frontier(game: Game) -> bool:
    board = set(game.hexes)
    radius = home_radius(game.rules.map_size)
    claimed: set[Hex] = set()
    for fort in game.fortresses:
        claimed.update(owned(fort.at(), radius, board, count=game.home_size))
    return len(claimed) < len(board)


def _home_notice(game: Game) -> None:
    if game.rules.visibility != "home":
        return
    for member in seated(game):
        notice(game, "home_land", member.player_id)

