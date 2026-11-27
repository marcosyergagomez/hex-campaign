"""Home disks, the first tokens, and the ground a seat may stand on."""

from hexcampaign.domain.chronicle import remember
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Army, Fortress, Game, Member, notice, seated
from hexcampaign.domain.hexes import DISK_RADIUS, Hex, angle, distance, neighbors
from hexcampaign.domain.land import home_radius, owned
from hexcampaign.domain.terrain import passable
from hexcampaign.domain.territory import assigned_homes, home_land


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

