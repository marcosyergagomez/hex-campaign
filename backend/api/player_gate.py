"""Session, origin and CSRF for a player request. Campaign routes add their own errors."""

from fastapi import Request
from fastapi.responses import JSONResponse

from api.player_session import (
    CSRF_COOKIE,
    CSRF_HEADER,
    CSRF_MESSAGE,
    ORIGIN_MESSAGE,
    SESSION_COOKIE,
    SESSION_MESSAGE,
    same_origin,
)
from apps.accounts.models import User
from apps.accounts.sessions import csrf_matches, load_session


def _errors(status: int, field: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"errors": {field: [message]}})


def reader(request: Request) -> User | JSONResponse:
    session = load_session(request.cookies.get(SESSION_COOKIE, ""))
    if session is None:
        return _errors(401, "session", SESSION_MESSAGE)
    return session.user


def writer(request: Request) -> User | JSONResponse:
    if not same_origin(request):
        return _errors(403, "origin", ORIGIN_MESSAGE)
    session = load_session(request.cookies.get(SESSION_COOKIE, ""))
    if session is None:
        return _errors(401, "session", SESSION_MESSAGE)
    if not csrf_matches(
        session,
        request.headers.get(CSRF_HEADER, ""),
        request.cookies.get(CSRF_COOKIE, ""),
    ):
        return _errors(403, "csrf", CSRF_MESSAGE)
    return session.user
