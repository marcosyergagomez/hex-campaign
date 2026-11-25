"""Saved maps. The picture belongs to one player and is copied into a campaign."""

import random

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.campaigns import _failure, _reader, _run
from api.player_session import django_sync
from apps.campaigns.atlases import list_maps, read_map, store_drawn, store_generated
from apps.campaigns.records import CampaignError

router = APIRouter()


class CellBody(BaseModel):
    q: int
    r: int
    ground: str
    road: bool = False
    bridge: bool = False


class MapBody(BaseModel):
    name: str
    size: int
    seats: int | None = None
    cells: list[CellBody] | None = None


@router.get("/api/maps")
@django_sync
def get_maps(request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    return JSONResponse(list_maps(user))


@router.get("/api/maps/{map_id}")
@django_sync
def get_map(map_id: str, request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return JSONResponse(read_map(user, map_id))
    except CampaignError as exc:
        return _failure(exc)


@router.post("/api/maps", status_code=201)
@django_sync
def post_map(payload: MapBody, request: Request) -> JSONResponse:
    def action(user):
        try:
            if payload.cells is None:
                if payload.seats is None:
                    raise CampaignError("rules_invalid")
                row = store_generated(
                    user,
                    payload.name,
                    payload.size,
                    payload.seats,
                    random.Random(),
                )
            else:
                cells = [item.model_dump() for item in payload.cells]
                row = store_drawn(user, payload.name, payload.size, cells)
        except CampaignError as exc:
            return _failure(exc)
        return JSONResponse(
            {"id": str(row.id), "name": row.name, "size": row.size, "generated": row.generated},
            status_code=201,
        )

    return _run(request, action)
