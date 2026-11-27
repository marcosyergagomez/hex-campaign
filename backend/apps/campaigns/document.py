"""Read and write the campaign JSON. Rules stay in the domain; this module only stores them."""

from collections.abc import Callable
from typing import Any

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import PHASES, Army, Battle, Fortress, Game, Member
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.identity import checked_identity
from hexcampaign.domain.land import checked_home_size
from hexcampaign.domain.rules import Rules, campaign_description, rules_from
from hexcampaign.domain.terrain import Plot, checked_plot
from hexcampaign.domain.units import checked_kind

VERSION = 2
SCHEMA_VERSION = 1


def to_dict(game: Game) -> dict[str, object]:
    return {
        "version": VERSION,
        "schema_version": SCHEMA_VERSION,
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
        "naming": game.naming,
        "fort_open": game.fort_open,
        "prep_done": sorted(game.prep_done),
        "fort_memory": {
            player_id: [
                {"q": int(key.split(",")[0]), "r": int(key.split(",")[1]), "owner": owner}
                for key, owner in sorted(memory.items())
            ]
            for player_id, memory in game.fort_memory.items()
        },
    }


def from_dict(data: object) -> Game:
    if not isinstance(data, dict):
        raise DomainError("rules_invalid")
    data = _migrate(data)
    if data.get("version") != VERSION:
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
    naming = data.get("naming", False)
    if not isinstance(naming, bool):
        raise DomainError("rules_invalid")
    game.naming = naming
    if "fort_open" in data:
        fort_open = data["fort_open"]
        if not isinstance(fort_open, bool):
            raise DomainError("rules_invalid")
        game.fort_open = fort_open
    else:
        game.fort_open = game.phase == "preparing" and not game.naming and not game.road_ready
    done = data.get("prep_done", [])
    if not isinstance(done, list) or any(not isinstance(item, str) for item in done):
        raise DomainError("rules_invalid")
    game.prep_done = set(done)
    _absorb_preparation(game)
    return game


def _migrate(data: dict[Any, Any]) -> dict[Any, Any]:
    """Bring a stored document up to SCHEMA_VERSION. Missing means the legacy shape."""
    current = _schema_number(data.get("schema_version"))
    if current is None:
        data = _from_legacy(data)
        current = SCHEMA_VERSION
    while current < SCHEMA_VERSION:
        step = _STEPS.get(current)
        if step is None:
            raise DomainError("rules_invalid")
        data = step(data)
        current += 1
    if current != SCHEMA_VERSION:
        raise DomainError("rules_invalid")
    return data


def _from_legacy(data: dict[Any, Any]) -> dict[Any, Any]:
    """Documents saved before schema_version already carry version 2. Keep every key."""
    if data.get("version") != VERSION:
        raise DomainError("rules_invalid")
    migrated = dict(data)
    migrated["schema_version"] = SCHEMA_VERSION
    return migrated


def _schema_number(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DomainError("rules_invalid")
    return value


# The next schema adds _STEPS[SCHEMA_VERSION] and raises SCHEMA_VERSION by one.
_STEPS: dict[int, Callable[[dict[Any, Any]], dict[Any, Any]]] = {}


def _absorb_preparation(game: Game) -> None:
    """Old saves waited between steps. Each seat now continues as far as it had reached."""
    if game.plots is None:
        return
    if game.phase == "placing":
        game.phase = "preparing"
        game.fort_open = True
    if game.phase != "preparing":
        return
    active = {member.player_id for member in game.members if member.status == "active"}
    if not game.fort_open:
        game.lobby_ready.update(active)
    if game.naming:
        game.road_ready.update(active)
        game.naming = False


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
        "roster_required": rules.roster_required,
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


def _list(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise DomainError("rules_invalid")
    return value


def _mapping(value: object) -> dict[Any, Any]:
    if not isinstance(value, dict):
        raise DomainError("rules_invalid")
    return value
