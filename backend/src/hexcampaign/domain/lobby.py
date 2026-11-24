"""Recruiting, the start button, and where the armies stand before the first order."""

from dataclasses import replace
from datetime import datetime

from hexcampaign.domain.clock import stamp
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
from hexcampaign.domain.rules import Rules, campaign_name, label, roster_text


def create_game(name: str, rules: Rules, owner_id: str, alias: str) -> Game:
    game = Game(
        revision=1,
        name=campaign_name(name),
        phase="recruiting",
        turn=0,
        rules=rules,
        hexes=list(disk(rules.map_size)),
    )
    game.members.append(Member(owner_id, alias, "owner", "active"))
    return game


def change_rules(game: Game, actor: str, name: str, rules: Rules) -> Game:
    require_owner(game, actor)
    require_phase(game, "recruiting")
    if rules.seats > game.rules.seats or rules.seats < len(seated(game)):
        raise DomainError("rules_invalid")
    game.name = campaign_name(name)
    game.rules = rules
    game.hexes = list(disk(rules.map_size))
    return bump(game)


def invite_player(game: Game, actor: str, invitee_id: str, alias: str) -> Game:
    require_owner(game, actor)
    require_phase(game, "recruiting")
    if not alias or len(alias) > 24:
        raise DomainError("rules_invalid")
    existing = find_member(game, invitee_id)
    if existing is not None and existing.status == "expelled":
        raise DomainError("expelled")
    if existing is not None:
        raise DomainError("already_joined")
    notice(game, "invited", invitee_id, alias=alias)
    return bump(game)


def accept_seat(game: Game, player_id: str, alias: str) -> Game:
    require_phase(game, "recruiting")
    if not alias or len(alias) > 24:
        raise DomainError("rules_invalid")
    existing = find_member(game, player_id)
    if existing is not None and existing.status == "expelled":
        raise DomainError("expelled")
    if existing is not None:
        raise DomainError("already_joined")
    if len(seated(game)) >= game.rules.seats:
        raise DomainError("seat_full")
    game.members.append(Member(player_id, alias, "player", "active"))
    return bump(game)


def begin(game: Game, actor: str, admin_ids: list[str], now: datetime) -> Game:
    require_owner(game, actor)
    require_phase(game, "recruiting")
    playing = seated(game)
    if len(playing) < 2 or len(playing) != game.rules.seats:
        raise DomainError("phase_invalid")
    known = {member.player_id for member in playing}
    if any(player_id not in known for player_id in admin_ids):
        raise DomainError("forbidden")
    for member in playing:
        if member.player_id in admin_ids and member.role != "owner":
            member.role = "admin"
    if game.rules.placement == "app":
        _deploy(game)
        game.phase = "orders"
        game.turn = 1
        game.orders_opened_at = stamp(now)
    else:
        _blank_armies(game)
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
    return bump(game)


def close_placement(game: Game, actor: str, now: datetime) -> Game:
    require_owner(game, actor)
    require_phase(game, "placing")
    for member in seated(game):
        if not any(fort.player_id == member.player_id for fort in game.fortresses):
            raise DomainError("phase_invalid")
    if any(army.at() is None for army in game.armies if not army.destroyed):
        raise DomainError("phase_invalid")
    _territory(game)
    game.phase = "orders"
    game.turn = 1
    game.orders_opened_at = stamp(now)
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
    require_phase(game, "placing", "orders", "battles")
    found = next((army for army in game.armies if army.id == army_id), None)
    if found is None or found.player_id != actor or found.destroyed:
        raise DomainError("forbidden")
    found.name = label(name, required=True)
    found.commander = label(commander, required=False)
    found.race = label(race, required=False)
    found.roster = roster_text(roster)
    return bump(game)


def _reject_overlap(game: Game, actor: str, cells: set[Hex]) -> None:
    for fort in game.fortresses:
        if fort.player_id != actor and fort.at() in cells:
            raise DomainError("order_illegal")
    for army in game.armies:
        if army.player_id != actor and army.at() in cells:
            raise DomainError("order_illegal")


def _deploy(game: Game) -> None:
    radius = DISK_RADIUS[game.rules.map_size]
    border = [cell for cell in game.hexes if distance(cell, Hex(0, 0)) == radius]
    border.sort(key=lambda cell: (angle(cell), cell.q, cell.r))
    players = seated(game)
    chosen = [border[(index * len(border)) // len(players)] for index in range(len(players))]
    taken = set(chosen)
    for member, fort in zip(players, chosen, strict=True):
        game.fortresses.append(Fortress(member.player_id, fort.q, fort.r))
        spots = [fort]
        if game.rules.armies == 2:
            spots.append(_beside(fort, taken, set(game.hexes)))
            taken.add(spots[-1])
        for number, spot in enumerate(spots, start=1):
            game.armies.append(_army(game, member.player_id, str(number), spot))
    _territory(game)


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
    return options[0]


def _territory(game: Game) -> None:
    forts = [(fort.at(), fort.player_id) for fort in game.fortresses]
    players = [member.player_id for member in seated(game)]
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
