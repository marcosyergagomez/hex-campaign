"""Player session cookies.

`__Host-session` is HttpOnly, so page scripts cannot read it. `__Host-csrf` is
readable and must come back in `X-CSRF-Token` on a request that changes state.
Both are Secure, SameSite=Lax, Path=/, and have no Domain, which is what the
`__Host-` prefix requires. The map has to be served on API_ORIGIN: another
origin does not receive this cookie.
"""

from functools import wraps
from urllib.parse import SplitResult, urlsplit

from django.conf import settings
from django.db import close_old_connections
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from apps.accounts.sessions import (
    LoginRejected,
    LoginThrottled,
    OpenedSession,
    csrf_matches,
    load_session,
    login,
)

router = APIRouter()

SESSION_COOKIE = "__Host-session"
CSRF_COOKIE = "__Host-csrf"
CSRF_HEADER = "x-csrf-token"

CREDENTIALS_MESSAGE = "El correo o la contraseña no son correctos."
SESSION_MESSAGE = "La sesión no es válida."
ORIGIN_MESSAGE = "La solicitud no viene de este sitio."
CSRF_MESSAGE = "La solicitud no es válida."
TOO_MANY_MESSAGE = "Demasiados intentos. Prueba de nuevo en unos minutos."


class LoginPayload(BaseModel):
    email: str
    password: str


def django_sync(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        close_old_connections()
        try:
            return view(*args, **kwargs)
        finally:
            close_old_connections()

    return wrapper


def same_origin(request: Request) -> bool:
    expected = urlsplit(settings.API_ORIGIN)
    origin = request.headers.get("origin", "")
    if origin:
        parsed = urlsplit(origin)
        return (
            _same_authority(parsed, expected)
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
    referer = request.headers.get("referer", "")
    if not referer:
        return False
    return _same_authority(urlsplit(referer), expected)


def _same_authority(parsed: SplitResult, expected: SplitResult) -> bool:
    return (
        parsed.scheme == expected.scheme
        and parsed.netloc == expected.netloc
        and parsed.username is None
        and parsed.password is None
    )


def _errors(status: int, field: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"errors": {field: [message]}})


def _set_session_cookies(response: Response, opened: OpenedSession) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        opened.token,
        max_age=opened.max_age,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE,
        opened.csrf_token,
        max_age=opened.max_age,
        path="/",
        secure=True,
        httponly=False,
        samesite="lax",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=True, httponly=False, samesite="lax")


@router.post(
    "/api/session",
    summary="Iniciar sesión",
    description=(
        "Solo una cuenta activa con el correo confirmado. "
        "Si el correo no existe, no está confirmado o la contraseña no coincide, "
        "la respuesta es la misma. Deja la sesión en una cookie HttpOnly."
    ),
    responses={401: {"description": "Credenciales rechazadas"}, 403: {"description": "Origen"}},
)
@django_sync
def open_player_session(payload: LoginPayload, request: Request) -> JSONResponse:
    if not same_origin(request):
        return _errors(403, "origin", ORIGIN_MESSAGE)
    try:
        opened = login(payload.email, payload.password)
    except LoginThrottled:
        return _errors(429, "credentials", TOO_MANY_MESSAGE)
    except LoginRejected:
        return _errors(401, "credentials", CREDENTIALS_MESSAGE)
    response = JSONResponse({"email": opened.user.email, "alias": opened.user.alias})
    _set_session_cookies(response, opened)
    return response


@router.get(
    "/api/session",
    summary="Quién ha iniciado sesión",
    responses={401: {"description": "Sin sesión"}},
)
@django_sync
def read_player_session(request: Request) -> JSONResponse:
    session = load_session(request.cookies.get(SESSION_COOKIE, ""))
    if session is None:
        return _errors(401, "session", SESSION_MESSAGE)
    user = session.user
    return JSONResponse({"email": user.email, "alias": user.alias})


@router.post(
    "/api/session/logout",
    status_code=204,
    summary="Cerrar esta sesión",
    description="Cierra solo el navegador que llama. El resto de sesiones siguen abiertas.",
)
@django_sync
def close_player_session(request: Request) -> Response:
    raw = request.cookies.get(SESSION_COOKIE, "")
    session = load_session(raw, touch=False)
    if session is None:
        response = Response(status_code=204)
        _clear_session_cookies(response)
        return response
    if not same_origin(request):
        return _errors(403, "origin", ORIGIN_MESSAGE)
    if not csrf_matches(
        session,
        request.headers.get(CSRF_HEADER, ""),
        request.cookies.get(CSRF_COOKIE, ""),
    ):
        return _errors(403, "csrf", CSRF_MESSAGE)
    session.delete()
    response = Response(status_code=204)
    _clear_session_cookies(response)
    return response
