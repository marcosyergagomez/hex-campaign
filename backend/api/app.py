"""HTTP contract for accounts. Django is configured before this module is imported."""

import json
from datetime import date
from functools import wraps
from typing import Literal
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

from api.guard import AccountGuard
from api.pages import confirm_page, result_page
from apps.accounts.registration import (
    ACCEPTED_DETAIL,
    InvalidConfirmation,
    MailDeliveryError,
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

INVALID_LINK = "El enlace no es válido o ha caducado."
CONFIRMED = "Correo confirmado."


class Accepted(BaseModel):
    detail: str


class ErrorBody(BaseModel):
    errors: dict[str, list[str]]


class RegisterPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str
    password: str
    alias: str
    birth_date: date
    sex: Literal["woman", "man", "other", "undisclosed"]


def django_sync(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        close_old_connections()
        try:
            return view(*args, **kwargs)
        finally:
            close_old_connections()

    return wrapper


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
    responses={422: {"model": ErrorBody}, 503: {"model": ErrorBody}},
)
@django_sync
def register_user(payload: RegisterPayload) -> JSONResponse | Accepted:
    try:
        register_account(
            email=payload.email,
            password=payload.password,
            alias=payload.alias,
            birth_date=payload.birth_date,
            sex=payload.sex,
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
def verify_email_page(token: str = "") -> HTMLResponse:
    if not token:
        return HTMLResponse(result_page(INVALID_LINK), status_code=400)
    return HTMLResponse(confirm_page(token))


def _confirm(raw_token: str) -> None:
    close_old_connections()
    try:
        confirm_email(raw_token)
    finally:
        close_old_connections()


@api.post(
    "/api/users/verify-email",
    response_model=Accepted,
    summary="Confirmar el correo",
    responses={400: {"model": ErrorBody}},
)
async def verify_email(request: Request) -> HTMLResponse | Accepted | JSONResponse:
    token, as_html = await _posted_token(request)
    try:
        await sync_to_async(_confirm)(token)
    except InvalidConfirmation:
        if as_html:
            return HTMLResponse(result_page(INVALID_LINK), status_code=400)
        return JSONResponse(status_code=400, content={"errors": {"token": [INVALID_LINK]}})
    if as_html:
        return HTMLResponse(result_page(CONFIRMED))
    return Accepted(detail=CONFIRMED)


async def _posted_token(request: Request) -> tuple[str, bool]:
    raw = await request.body()
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return "", False
        token = data.get("token", "") if isinstance(data, dict) else ""
        return (token if isinstance(token, str) else ""), False
    parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
    return parsed.get("token", [""])[0], True
