"""Request bodies for the campaign HTTP API."""

from pydantic import BaseModel, Field


class RulesBody(BaseModel):
    seats: int
    armies: int
    movement: int
    map_size: int
    visibility: str
    victory: str
    hold_turns: int
    placement: str
    order_days: int
    battle_days: int
    missed_turns: int
    roster_required: bool = False


class CreateBody(BaseModel):
    name: str
    rules: RulesBody
    description: str = ""
    map_id: str | None = None
    blind: bool = False


class RevisionBody(BaseModel):
    revision: int


class ReadyBody(RevisionBody):
    ready: bool = True


class IdentityBody(RevisionBody):
    faction: str
    color: str


class ColorBody(RevisionBody):
    color: str


class RulesChange(BaseModel):
    revision: int
    name: str
    rules: RulesBody
    description: str | None = None


class AliasBody(BaseModel):
    revision: int
    alias: str


class StartBody(BaseModel):
    revision: int
    admins: list[str] = Field(default_factory=list)


class HexBody(BaseModel):
    q: int
    r: int


class PlaceBody(BaseModel):
    revision: int
    fortress: HexBody
    armies: dict[str, HexBody]


class RoadBody(BaseModel):
    revision: int
    q: int
    r: int


class ArmyBody(BaseModel):
    revision: int
    name: str
    commander: str = ""
    race: str = ""
    roster: str = ""


class OrdersBody(BaseModel):
    revision: int
    orders: dict[str, list[HexBody]]


class BattleBody(BaseModel):
    revision: int
    result: str


class PlayerBody(BaseModel):
    revision: int
    player_id: str


class ScrapBody(BaseModel):
    confirm_name: str
