"""Recruiting, the start button, and where the armies stand before the first order."""

from dataclasses import replace
from datetime import datetime

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
    seated,
)
from hexcampaign.domain.hexes import DISK_RADIUS, Hex, angle, disk, distance, neighbors
from hexcampaign.domain.identity import checked_identity
from hexcampaign.domain.land import home_radius, owned
from hexcampaign.domain.phases import open_first_turn, open_preparation
from hexcampaign.domain.rules import Rules, campaign_description, campaign_name, label, roster_text
from hexcampaign.domain.terrain import passable
from hexcampaign.domain.territory import home_land


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
    require_owner(game, actor)
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
        else:
            open_first_turn(game, now)
    else:
        _blank_armies(game)
        if game.plots is not None:
            _open_player_homes(game)
        game.phase = "placing"
    return bump(game)


def place_armies(game: Game, actor: str, fortress: Hex, spots: dict[str, Hex]) -> Game:
    require_phase(game, "placing")
    require_player(game, actor)
    own = [army for army in game.armies if army.player_id == actor and not army.destroyed]
    board = set(game.hexes)
    if set(spots) != {army.id for army in own}:
        raise DomainError("order_illegal")
    if fortress not in board or any(spot not in board for spot in spots.values()):
        raise DomainError("order_illegal")
    if game.plots is not None and (
        not _standable(game, fortress) or any(not _standable(game, spot) for spot in spots.values())
    ):
        raise DomainError("order_illegal")
    home = _player_home_zone(game, actor) if game.plots is not None else None
    if home is not None and fortress not in home:
        raise DomainError("order_illegal")
    if game.plots is not None and _disks_overlap(game, actor, fortress):
        raise DomainError("order_illegal")
    if home is not None and any(spot not in home for spot in spots.values()):
        raise DomainError("order_illegal")
    if len({fortress, *spots.values()}) != 1 + len(spots):
        raise DomainError("order_illegal")
    _reject_overlap(game, actor, {fortress, *spots.values()})
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
    if game.plots is not None and not _frontier(game):
        raise DomainError("phase_invalid")
    _territory(game)
    _home_notice(game)
    remember(game, "placement_closed", player_id=actor)
    if game.plots is not None:
        open_preparation(game)
    else:
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
) -> Game:
    require_phase(game, "placing", "preparing", "orders", "battles")
    found = next((army for army in game.armies if army.id == army_id), None)
    if found is None or found.player_id != actor or found.destroyed:
        raise DomainError("forbidden")
    found.name = label(name, required=True)
    found.commander = label(commander, required=False)
    found.race = label(race, required=False)
    found.roster = roster_text(roster)
    remember(game, "named", player_id=actor, army_id=found.id, name=found.name)
    return bump(game)


def _reject_overlap(game: Game, actor: str, cells: set[Hex]) -> None:
    for fort in game.fortresses:
        if fort.player_id != actor and fort.at() in cells:
            raise DomainError("order_illegal")
    for army in game.armies:
        if army.player_id != actor and army.at() in cells:
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
    for member, fort in zip(players, chosen, strict=True):
        if game.plots is not None and not _standable(game, fort):
            raise DomainError("rules_invalid")
        game.fortresses.append(Fortress(member.player_id, fort.q, fort.r))
        spots = [fort]
        if game.rules.armies == 2:
            spots.append(_beside(fort, taken, _stand_board(game)))
            taken.add(spots[-1])
        for number, spot in enumerate(spots, start=1):
            game.armies.append(_army(game, member.player_id, str(number), spot))
    _territory(game)
    _home_notice(game)


def _blank_armies(game: Game) -> None:
    for member in seated(game):
        for number in range(1, game.rules.armies + 1):
            game.armies.append(_army(game, member.player_id, str(number), None))


def _army(game: Game, player_id: str, name: str, spot: Hex | None) -> Army:
    army = Army(
        id=f"a{game.next_id}",
        player_id=player_id,
        name=name,
        commander="",
        race="",
        roster="",
        q=None if spot is None else spot.q,
        r=None if spot is None else spot.r,
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
        _grant_surveyor(game)
        return
    if game.plots is not None and game.rules.visibility == "home":
        board = set(game.hexes)
        for player_id in players:
            game.discovered[player_id] = home_land(game, player_id, board=board)
        _grant_surveyor(game)
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


def _grant_surveyor(game: Game) -> None:
    if game.surveyor:
        game.discovered[game.surveyor] = set(game.hexes)
