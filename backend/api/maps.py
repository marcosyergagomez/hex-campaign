"""Saved maps. The picture belongs to one player and is copied into a campaign."""

import random

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from api.player_gate import reader, writer
from api.player_session import SESSION_MESSAGE, django_sync
from apps.campaigns.atlases import (
    copy_for_edit,
    drop_map,
    list_maps,
    read_map,
    store_drawn,
    store_generated,
    update_drawn,
)
from apps.campaigns.records import CampaignError
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.maps import table_presets

router = APIRouter()

_MESSAGES = {
    "rules_invalid": "Las reglas no son válidas.",
    "map_unknown": "No hay ningún mapa con ese identificador.",
    "map_limit": "Ya tienes el máximo de mapas guardados.",
    "map_readonly": "Ese mapa generado no se puede sobrescribir; crea una copia.",
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
    elif exc.code == "map_readonly":
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


def _summary(row) -> dict[str, object]:
    return {
        "id": str(row.id),
        "name": row.name,
        "size": row.size,
        "seats": row.seats,
        "generated": row.generated,
    }


class CellBody(BaseModel):
    q: int
    r: int
    ground: str
    road: bool = False
    bridge: bool = False


class AnchorBody(BaseModel):
    q: int
    r: int


class MapBody(BaseModel):
    name: str
    size: int
    seats: int | None = None
    cells: list[CellBody] | None = None
    anchors: list[AnchorBody] = Field(default_factory=list)


class CopyBody(BaseModel):
    name: str | None = None


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
                anchors = [item.model_dump() for item in payload.anchors]
                row = store_drawn(user, payload.name, payload.size, cells, anchors)
        except (CampaignError, DomainError) as exc:
            return _failure(CampaignError(exc.code))
        return JSONResponse(_summary(row), status_code=201)

    return _run(request, action)


@router.put("/api/maps/{map_id}")
@django_sync
def put_map(map_id: str, payload: MapBody, request: Request) -> JSONResponse:
    def action(user):
        if payload.cells is None:
            raise CampaignError("rules_invalid")
        cells = [item.model_dump() for item in payload.cells]
        anchors = [item.model_dump() for item in payload.anchors]
        try:
            row = update_drawn(user, map_id, payload.name, payload.size, cells, anchors)
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
        return JSONResponse(_summary(row))

    return _run(request, action)


@router.post("/api/maps/{map_id}/copy", status_code=201)
@django_sync
def post_map_copy(map_id: str, payload: CopyBody, request: Request) -> JSONResponse:
    def action(user):
        row = copy_for_edit(user, map_id, payload.name)
        return JSONResponse(_summary(row), status_code=201)

    return _run(request, action)
