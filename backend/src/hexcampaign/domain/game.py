"""The campaign document. Persistence stores this mapping; it does not decide the rules."""

from dataclasses import dataclass, field

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.identity import checked_identity
from hexcampaign.domain.land import checked_home_size
from hexcampaign.domain.rules import Rules, campaign_description, rules_from
from hexcampaign.domain.terrain import Plot, checked_plot
from hexcampaign.domain.units import checked_kind

VERSION = 2
PHASES = frozenset({"recruiting", "placing", "preparing", "orders", "battles", "finished"})


@dataclass
class Member:
    player_id: str
    alias: str
    role: str
    status: str
    missed: int = 0
    cause: str = ""
    faction: str = ""
    color: str = ""


@dataclass
class Army:
    id: str
    player_id: str
    name: str
    commander: str
    race: str
    roster: str
    q: int | None
    r: int | None
    destroyed: bool = False
    paid: int = 0
    kind: str = "army"

    def at(self) -> Hex | None:
        if self.q is None or self.r is None:
            return None
        return Hex(self.q, self.r)


@dataclass
class Fortress:
    player_id: str
    q: int
    r: int
    holder_id: str | None = None
    hold: int = 0

    def at(self) -> Hex:
        return Hex(self.q, self.r)


@dataclass
class Battle:
    id: str
    turn: int
    q: int
    r: int
    army_ids: list[str]
    players: list[str]
    reports: dict[str, str]
    result: str | None
    reverted: bool
    opened_at: str


@dataclass
class Game:
    revision: int
    name: str
    phase: str
    turn: int
    rules: Rules
    hexes: list[Hex]
    description: str = ""
    members: list[Member] = field(default_factory=list)
    armies: list[Army] = field(default_factory=list)
    fortresses: list[Fortress] = field(default_factory=list)
    discovered: dict[str, set[Hex]] = field(default_factory=dict)
    orders: dict[str, dict[str, tuple[Hex, ...]]] = field(default_factory=dict)
    battles: list[Battle] = field(default_factory=list)
    notices: list[dict[str, str]] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    chronicle: list[dict[str, object]] = field(default_factory=list)
    winners: list[str] = field(default_factory=list)
    orders_opened_at: str | None = None
    previous: dict | None = None
    next_id: int = 1
    plots: dict[Hex, Plot] | None = None
    anchors: list[Hex] = field(default_factory=list)
    surveyor: str | None = None
    fort_memory: dict[str, dict[str, str | None]] = field(default_factory=dict)
    home_size: int | None = None
    identity_required: bool = False
    road_ready: set[str] = field(default_factory=set)
    lobby_ready: set[str] = field(default_factory=set)


def find_member(game: Game, player_id: str) -> Member | None:
    for member in game.members:
        if member.player_id == player_id:
            return member
    return None


def find_army(game: Game, army_id: str) -> Army | None:
    for army in game.armies:
        if army.id == army_id:
            return army
    return None


def seated(game: Game) -> list[Member]:
    return [member for member in game.members if member.status != "expelled"]


def living(game: Game, player_id: str | None = None) -> list[Army]:
    found: list[Army] = []
    for army in game.armies:
        if army.destroyed or army.q is None or army.r is None:
            continue
        if player_id is not None and army.player_id != player_id:
            continue
        found.append(army)
    return found


def living_fighters(game: Game, player_id: str | None = None) -> list[Army]:
    return [army for army in living(game, player_id) if army.kind == "army"]


def require_member(game: Game, player_id: str) -> Member:
    member = find_member(game, player_id)
    if member is None or member.status == "expelled":
        raise DomainError("forbidden")
    return member


def require_player(game: Game, player_id: str) -> Member:
    """Only an active seat may issue player commands (orders, roads, ready, …)."""
    member = require_member(game, player_id)
    if member.status != "active":
        raise DomainError("forbidden")
    return member


def require_staff(game: Game, player_id: str) -> Member:
    member = require_member(game, player_id)
    if member.role not in {"owner", "admin"} or member.status != "active":
        raise DomainError("forbidden")
    return member


def require_owner(game: Game, player_id: str) -> Member:
    member = require_member(game, player_id)
    if member.role != "owner" or member.status != "active":
        raise DomainError("forbidden")
    return member


def require_phase(game: Game, *phases: str) -> None:
    if game.phase not in phases:
        raise DomainError("phase_invalid")


def bump(game: Game) -> Game:
    game.revision += 1
    return game


def notice(game: Game, code: str, player_id: str, **extra: str) -> None:
    game.notices.append({"code": code, "player_id": player_id, **extra})
    del game.notices[:-30]


def to_dict(game: Game) -> dict[str, object]:
    return {
        "version": VERSION,
        "revision": game.revision,
        "name": game.name,
        "description": game.description,
        "phase": game.phase,
        "turn": game.turn,
        "rules": _rules_dict(game.rules),
        "hexes": [_hex(cell) for cell in game.hexes],
        "members": [_member_dict(member) for member in game.members],
        "armies": [_army_dict(army) for army in game.armies],
        "fortresses": [_fort_dict(fort) for fort in game.fortresses],
        "discovered": {
            player_id: [_hex(cell) for cell in sorted(cells)]
            for player_id, cells in game.discovered.items()
        },
        "orders": {
            player_id: {army_id: [_hex(cell) for cell in path] for army_id, path in orders.items()}
            for player_id, orders in game.orders.items()
        },
        "battles": [_battle_dict(battle) for battle in game.battles],
        "notices": [dict(item) for item in game.notices],
        "events": [dict(item) for item in game.events],
        "chronicle": [dict(item) for item in game.chronicle],
        "winners": list(game.winners),
        "orders_opened_at": game.orders_opened_at,
        "previous": game.previous,
        "next_id": game.next_id,
        "plots": _stored_plots(game),
        "anchors": [_hex(cell) for cell in game.anchors],
        "surveyor": game.surveyor,
        "home_size": game.home_size,
        "identity_required": game.identity_required,
        "road_ready": sorted(game.road_ready),
        "lobby_ready": sorted(game.lobby_ready),
        "fort_memory": {
            player_id: [
                {"q": int(key.split(",")[0]), "r": int(key.split(",")[1]), "owner": owner}
                for key, owner in sorted(memory.items())
            ]
            for player_id, memory in game.fort_memory.items()
        },
    }


def from_dict(data: object) -> Game:
    if not isinstance(data, dict) or data.get("version") != VERSION:
        raise DomainError("rules_invalid")
    phase = data["phase"]
    if phase not in PHASES:
        raise DomainError("rules_invalid")
    previous = data["previous"]
    if previous is not None and not isinstance(previous, dict):
        raise DomainError("rules_invalid")
    opened = data["orders_opened_at"]
    if opened is not None and not isinstance(opened, str):
        raise DomainError("rules_invalid")
    game = Game(
        revision=_whole(data["revision"]),
        name=str(data["name"]),
        phase=str(phase),
        turn=_whole(data["turn"]),
        rules=rules_from(data["rules"], floor=0),
        hexes=[_cell(item) for item in _list(data["hexes"])],
        description=campaign_description(data["description"] if "description" in data else ""),
        orders_opened_at=opened,
        previous=previous,
        winners=[str(item) for item in _list(data["winners"])],
        next_id=_whole(data["next_id"]),
    )
    game.members = [_member(item) for item in _list(data["members"])]
    game.armies = [_army(item) for item in _list(data["armies"])]
    game.fortresses = [_fort(item) for item in _list(data["fortresses"])]
    game.discovered = {
        str(player_id): {_cell(item) for item in _list(cells)}
        for player_id, cells in _mapping(data["discovered"]).items()
    }
    game.orders = {
        str(player_id): {
            str(army_id): tuple(_cell(item) for item in _list(path))
            for army_id, path in _mapping(orders).items()
        }
        for player_id, orders in _mapping(data["orders"]).items()
    }
    game.battles = [_battle(item) for item in _list(data["battles"])]
    game.notices = [_text_map(item) for item in _list(data["notices"])]
    game.events = [dict(_mapping(item)) for item in _list(data["events"])]
    saved = data.get("chronicle", [])
    if not isinstance(saved, list):
        raise DomainError("rules_invalid")
    game.chronicle = [dict(_mapping(item)) for item in saved]
    game.plots = _plots(data.get("plots"))
    game.home_size = checked_home_size(data.get("home_size"), game.rules.map_size)
    identity_required = data.get("identity_required", False)
    if not isinstance(identity_required, bool):
        raise DomainError("rules_invalid")
    game.identity_required = identity_required
    game.anchors = [_cell(item) for item in _list(data["anchors"])] if "anchors" in data else []
    surveyor = data.get("surveyor")
    game.surveyor = None if surveyor is None else str(surveyor)
    game.fort_memory = _memory(data.get("fort_memory", {}))
    ready = data.get("road_ready", [])
    if not isinstance(ready, list) or any(not isinstance(item, str) for item in ready):
        raise DomainError("rules_invalid")
    game.road_ready = set(ready)
    lobby = data.get("lobby_ready", [])
    if not isinstance(lobby, list) or any(not isinstance(item, str) for item in lobby):
        raise DomainError("rules_invalid")
    game.lobby_ready = set(lobby)
    return game


def _rules_dict(rules: Rules) -> dict[str, object]:
    return {
        "seats": rules.seats,
        "armies": rules.armies,
        "movement": rules.movement,
        "map_size": rules.map_size,
        "visibility": rules.visibility,
        "victory": rules.victory,
        "hold_turns": rules.hold_turns,
        "placement": rules.placement,
        "order_days": rules.order_days,
        "battle_days": rules.battle_days,
        "missed_turns": rules.missed_turns,
    }


def _member_dict(member: Member) -> dict[str, object]:
    return {
        "player_id": member.player_id,
        "alias": member.alias,
        "role": member.role,
        "status": member.status,
        "missed": member.missed,
        "cause": member.cause,
        "faction": member.faction,
        "color": member.color,
    }


def _army_dict(army: Army) -> dict[str, object]:
    return {
        "id": army.id,
        "player_id": army.player_id,
        "name": army.name,
        "commander": army.commander,
        "race": army.race,
        "roster": army.roster,
        "q": army.q,
        "r": army.r,
        "destroyed": army.destroyed,
        "paid": army.paid,
        "kind": army.kind,
    }


def _fort_dict(fort: Fortress) -> dict[str, object]:
    return {
        "player_id": fort.player_id,
        "q": fort.q,
        "r": fort.r,
        "holder_id": fort.holder_id,
        "hold": fort.hold,
    }


def _battle_dict(battle: Battle) -> dict[str, object]:
    return {
        "id": battle.id,
        "turn": battle.turn,
        "q": battle.q,
        "r": battle.r,
        "army_ids": list(battle.army_ids),
        "players": list(battle.players),
        "reports": dict(battle.reports),
        "result": battle.result,
        "reverted": battle.reverted,
        "opened_at": battle.opened_at,
    }


def _member(data: object) -> Member:
    raw = _mapping(data)
    faction, color = checked_identity(raw.get("faction", ""), raw.get("color", ""), optional=True)
    return Member(
        player_id=str(raw["player_id"]),
        alias=str(raw["alias"]),
        role=str(raw["role"]),
        status=str(raw["status"]),
        missed=_whole(raw["missed"]),
        cause=str(raw["cause"]),
        faction=faction,
        color=color,
    )


def _army(data: object) -> Army:
    raw = _mapping(data)
    return Army(
        id=str(raw["id"]),
        player_id=str(raw["player_id"]),
        name=str(raw["name"]),
        commander=str(raw["commander"]),
        race=str(raw["race"]),
        roster=str(raw["roster"]),
        q=_optional_whole(raw["q"]),
        r=_optional_whole(raw["r"]),
        destroyed=bool(raw["destroyed"]),
        paid=_whole(raw["paid"]) if "paid" in raw else 0,
        kind=checked_kind(raw["kind"]) if "kind" in raw else "army",
    )


def _fort(data: object) -> Fortress:
    raw = _mapping(data)
    holder = raw["holder_id"]
    return Fortress(
        player_id=str(raw["player_id"]),
        q=_whole(raw["q"]),
        r=_whole(raw["r"]),
        holder_id=None if holder is None else str(holder),
        hold=_whole(raw["hold"]),
    )


def _battle(data: object) -> Battle:
    raw = _mapping(data)
    result = raw["result"]
    reports = _mapping(raw["reports"])
    return Battle(
        id=str(raw["id"]),
        turn=_whole(raw["turn"]),
        q=_whole(raw["q"]),
        r=_whole(raw["r"]),
        army_ids=[str(item) for item in _list(raw["army_ids"])],
        players=[str(item) for item in _list(raw["players"])],
        reports={str(key): str(value) for key, value in reports.items()},
        result=None if result is None else str(result),
        reverted=bool(raw["reverted"]),
        opened_at=str(raw["opened_at"]),
    )


def _text_map(data: object) -> dict[str, str]:
    return {str(key): str(value) for key, value in _mapping(data).items()}


def _stored_plots(game: Game) -> list[dict[str, object]] | None:
    if game.plots is None:
        return None
    return [_plot_dict(cell, plot) for cell, plot in sorted(game.plots.items())]


def _plot_dict(cell: Hex, plot: Plot) -> dict[str, object]:
    return {
        "q": cell.q,
        "r": cell.r,
        "ground": plot.ground,
        "road": plot.road,
        "bridge": plot.bridge,
    }


def _plots(value: object) -> dict[Hex, Plot] | None:
    if value is None:
        return None
    found: dict[Hex, Plot] = {}
    for item in _list(value):
        raw = _mapping(item)
        cell = Hex(_whole(raw["q"]), _whole(raw["r"]))
        if cell in found:
            raise DomainError("rules_invalid")
        found[cell] = checked_plot(raw["ground"], bool(raw["road"]), bool(raw["bridge"]))
    return found


def _memory(value: object) -> dict[str, dict[str, str | None]]:
    if not isinstance(value, dict):
        raise DomainError("rules_invalid")
    memory: dict[str, dict[str, str | None]] = {}
    for player_id, rows in value.items():
        kept: dict[str, str | None] = {}
        for item in _list(rows):
            raw = _mapping(item)
            owner = raw["owner"]
            kept[f"{_whole(raw['q'])},{_whole(raw['r'])}"] = None if owner is None else str(owner)
        memory[str(player_id)] = kept
    return memory


def _hex(cell: Hex) -> dict[str, int]:
    return {"q": cell.q, "r": cell.r}


def _cell(data: object) -> Hex:
    raw = _mapping(data)
    return Hex(_whole(raw["q"]), _whole(raw["r"]))


def _whole(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainError("rules_invalid")
    return value


def _optional_whole(value: object) -> int | None:
    if value is None:
        return None
    return _whole(value)


def _list(value: object) -> list:
    if not isinstance(value, list):
        raise DomainError("rules_invalid")
    return value


def _mapping(value: object) -> dict:
    if not isinstance(value, dict):
        raise DomainError("rules_invalid")
    return value
