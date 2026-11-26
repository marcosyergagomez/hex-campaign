"""Saved maps. The picture belongs to one player and is copied into a campaign."""

import random

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from api.player_gate import reader, writer
from api.player_session import SESSION_MESSAGE, django_sync
from apps.campaigns.atlases import drop_map, list_maps, read_map, store_drawn, store_generated
from apps.campaigns.records import CampaignError
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.maps import table_presets

router = APIRouter()

_MESSAGES = {
    "rules_invalid": "Las reglas no son válidas.",
    "map_unknown": "No hay ningún mapa con ese identificador.",
    "map_limit": "Ya tienes el máximo de mapas guardados.",
}


def _failure(exc: CampaignError) -> JSONResponse:
    if exc.code == "account_inactive":
        return JSONResponse(
            status_code=401,
            content={"errors": {"session": [SESSION_MESSAGE]}},
        )
    if exc.code == "map_unknown":
        status, field = 404, "map"
    elif exc.code == "map_limit":
        status, field = 422, "map"
    else:
        status, field = 422, "rules"
    message = _MESSAGES.get(exc.code, _MESSAGES["rules_invalid"])
    return JSONResponse(status_code=status, content={"errors": {field: [message]}})


def _run(request: Request, action) -> Response:
    user = writer(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return action(user)
    except CampaignError as exc:
        return _failure(exc)


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


@router.get("/api/map-scales")
@django_sync
def get_map_scales(request: Request) -> JSONResponse:
    user = reader(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return JSONResponse(table_presets())
    except DomainError as exc:
        return _failure(CampaignError(exc.code))


@router.get("/api/maps")
@django_sync
def get_maps(request: Request) -> JSONResponse:
    user = reader(request)
    if isinstance(user, JSONResponse):
        return user
    return JSONResponse(list_maps(user))


@router.get("/api/maps/{map_id}")
@django_sync
def get_map(map_id: str, request: Request) -> JSONResponse:
    user = reader(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return JSONResponse(read_map(user, map_id))
    except CampaignError as exc:
        return _failure(exc)


@router.delete("/api/maps/{map_id}", status_code=204)
@django_sync
def delete_map(map_id: str, request: Request) -> Response:
    def action(user):
        drop_map(user, map_id)
        return Response(status_code=204)

    return _run(request, action)


@router.post("/api/maps", status_code=201)
@django_sync
def post_map(payload: MapBody, request: Request) -> JSONResponse:
    def action(user):
        try:
            if payload.cells is None:
                sizes = {row["size"] for row in table_presets()}
                if payload.seats is None or payload.size not in sizes:
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
        except (CampaignError, DomainError) as exc:
            return _failure(CampaignError(exc.code))
        return JSONResponse(
            {
                "id": str(row.id),
                "name": row.name,
                "size": row.size,
                "seats": row.seats,
                "generated": row.generated,
            },
            status_code=201,
        )

    return _run(request, action)
