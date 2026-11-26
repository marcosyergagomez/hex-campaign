"""HTTP contract for accounts. Django is configured before this module is imported."""

import json
from datetime import date
from typing import Literal
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from api.campaigns import router as campaign_router
from api.django_db import django_sync
from api.guard import AccountGuard
from api.maps import router as map_router
from api.pages import confirm_page, result_page
from api.player_session import ORIGIN_MESSAGE, same_origin
from api.player_session import router as player_session_router
from apps.accounts.languages import normalize
from apps.accounts.registration import (
    ACCEPTED_DETAIL,
    PASSWORD_MISMATCH,
    InvalidConfirmation,
    MailDeliveryError,
    PasswordMismatch,
    RegistrationError,
    confirm_email,
    register_account,
)
from apps.accounts.validation import SEX_MESSAGE

api = FastAPI(
    title="Hex Campaign",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)
api.add_middleware(AccountGuard)
api.include_router(player_session_router)
api.include_router(campaign_router)
api.include_router(map_router)

INVALID_LINK = "El enlace no es válido o ha caducado."
CONFIRMED = "Correo confirmado."


class Accepted(BaseModel):
    detail: str


class ErrorBody(BaseModel):
    errors: dict[str, list[str]]


class RegisterPayload(BaseModel):
    email: str
    password: str
    alias: str
    birth_date: date
    sex: Literal["woman", "man", "other", "undisclosed"]


def _field_name(location: tuple[object, ...]) -> str:
    parts = [part for part in location if part not in {"body", "query", "path"}]
    return str(parts[0]) if parts else "body"


def _validation_message(field: str, error_type: str) -> str:
    if field == "sex":
        return SEX_MESSAGE
    if error_type == "missing":
        return "Este campo es obligatorio."
    return "Dato no válido."


@api.exception_handler(RequestValidationError)
async def reject_invalid_body(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors: dict[str, list[str]] = {}
    for error in exc.errors():
        field = _field_name(tuple(error.get("loc", ())))
        message = _validation_message(field, str(error.get("type", "")))
        errors.setdefault(field, [])
        if message not in errors[field]:
            errors[field].append(message)
    return JSONResponse(status_code=422, content={"errors": errors})


@api.post(
    "/api/users",
    status_code=202,
    response_model=Accepted,
    summary="Registrar una cuenta",
    description=(
        "Crea la cuenta y envía el enlace de confirmación. "
        "Si el correo ya está confirmado, responde 422. "
        "Si el alta anterior no se confirmó, la nueva la sustituye."
    ),
    responses={422: {"model": ErrorBody}, 503: {"model": ErrorBody}},
)
@django_sync
def register_user(payload: RegisterPayload, request: Request) -> JSONResponse | Accepted:
    if not same_origin(request):
        return JSONResponse(status_code=403, content={"errors": {"origin": [ORIGIN_MESSAGE]}})
    try:
        register_account(
            email=payload.email,
            password=payload.password,
            alias=payload.alias,
            birth_date=payload.birth_date,
            sex=payload.sex,
            language=normalize(request.cookies.get("hex_lang")),
        )
    except RegistrationError as exc:
        return JSONResponse(status_code=422, content={"errors": exc.errors})
    except MailDeliveryError:
        return JSONResponse(
            status_code=503,
            content={"errors": {"email": ["No se ha podido enviar el correo."]}},
        )
    return Accepted(detail=ACCEPTED_DETAIL)


@api.get("/api/users/verify-email", summary="Página para confirmar el correo")
def verify_email_page(request: Request, token: str = "", lang: str = "") -> HTMLResponse:
    language = normalize(lang or request.cookies.get("hex_lang"))
    if not token:
        response = HTMLResponse(result_page(INVALID_LINK, language), status_code=400)
    else:
        response = HTMLResponse(confirm_page(token, language=language))
    if lang in {"en", "es", "fr", "it", "de"}:
        response.set_cookie(
            "hex_lang",
            language,
            max_age=60 * 60 * 24 * 365,
            path="/",
            samesite="lax",
            secure=request.url.scheme == "https",
        )
    return response


def _confirm(raw_token: str, password: str) -> None:
    close_old_connections()
    try:
        confirm_email(raw_token, password)
    finally:
        close_old_connections()


@api.post(
    "/api/users/verify-email",
    response_model=Accepted,
    summary="Confirmar el correo",
    description="El enlace solo confirma la cuenta si la contraseña es la del alta.",
    responses={400: {"model": ErrorBody}},
)
async def verify_email(request: Request) -> HTMLResponse | Accepted | JSONResponse:
    token, password, as_html, language = await _posted_credentials(request)
    try:
        await sync_to_async(_confirm)(token, password)
    except InvalidConfirmation:
        if as_html:
            return HTMLResponse(result_page(INVALID_LINK, language), status_code=400)
        return JSONResponse(status_code=400, content={"errors": {"token": [INVALID_LINK]}})
    except PasswordMismatch:
        if as_html:
            return HTMLResponse(confirm_page(token, PASSWORD_MISMATCH, language), status_code=400)
        return JSONResponse(
            status_code=400,
            content={"errors": {"password": [PASSWORD_MISMATCH]}},
        )
    if as_html:
        return HTMLResponse(result_page(CONFIRMED, language))
    return Accepted(detail=CONFIRMED)


async def _posted_credentials(request: Request) -> tuple[str, str, bool, str]:
    raw = await request.body()
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return "", "", False, "es"
        if not isinstance(data, dict):
            return "", "", False, "es"
        token = data.get("token", "")
        password = data.get("password", "")
        return (
            token if isinstance(token, str) else "",
            password if isinstance(password, str) else "",
            False,
            "es",
        )
    parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
    return (
        parsed.get("token", [""])[0],
        parsed.get("password", [""])[0],
        True,
        normalize(parsed.get("lang", [""])[0]),
    )
