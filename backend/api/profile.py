"""Signed-in player profile: read and update personal data."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.django_db import django_sync
from api.player_gate import reader, writer
from api.player_session import set_session_cookies
from apps.accounts.passwords import HashBusy
from apps.accounts.profile import ProfileRejected, public_profile, update_profile
from apps.accounts.sessions import open_session

router = APIRouter()


class ProfilePayload(BaseModel):
    alias: str
    sex: str
    password: str | None = None
    current_password: str | None = None


@router.get(
    "/api/profile",
    summary="Datos del jugador",
    responses={401: {"description": "Sin sesión"}},
)
@django_sync
def read_profile(request: Request) -> JSONResponse:
    user = reader(request)
    if isinstance(user, JSONResponse):
        return user
    return JSONResponse(public_profile(user))


@router.post(
    "/api/profile",
    summary="Actualizar datos del jugador",
    responses={
        400: {"description": "Datos rechazados"},
        401: {"description": "Sin sesión"},
        403: {"description": "Origen o CSRF"},
    },
)
@django_sync
def write_profile(payload: ProfilePayload, request: Request) -> JSONResponse:
    user = writer(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        updated = update_profile(
            user,
            alias=payload.alias,
            sex=payload.sex,
            password=payload.password,
            current_password=payload.current_password,
        )
    except ProfileRejected as rejected:
        return JSONResponse(status_code=400, content={"errors": rejected.errors})
    except HashBusy:
        return JSONResponse(
            status_code=429,
            content={
                "errors": {
                    "password": ["Demasiados intentos. Prueba de nuevo en unos minutos."],
                }
            },
        )
    response = JSONResponse(public_profile(updated.user))
    if updated.password_changed:
        # Password save revoked every cookie; mint a fresh one for this browser.
        set_session_cookies(response, open_session(updated.user))
    return response
