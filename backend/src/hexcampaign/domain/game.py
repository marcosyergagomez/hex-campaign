"""Campaign types. Persistence stores the mapping; this module does not decide the rules."""

from dataclasses import dataclass, field
from typing import Any

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.rules import Rules
from hexcampaign.domain.terrain import Plot

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
    previous: dict[str, Any] | None = None
    next_id: int = 1
    plots: dict[Hex, Plot] | None = None
    anchors: list[Hex] = field(default_factory=list)
    surveyor: str | None = None
    fort_memory: dict[str, dict[str, str | None]] = field(default_factory=dict)
    home_size: int | None = None
    identity_required: bool = False
    road_ready: set[str] = field(default_factory=set)
    lobby_ready: set[str] = field(default_factory=set)
    naming: bool = False
    fort_open: bool = False
    prep_done: set[str] = field(default_factory=set)


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
