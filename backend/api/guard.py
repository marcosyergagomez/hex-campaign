"""Bounds and response headers for the account and session routes.

The confirmation page carries a secret in the query string, so responses are
not cached and do not send a referrer. Posts are capped so a large body never
reaches the hasher.
"""

import json
from collections.abc import Awaitable, Callable

from django.conf import settings
from starlette.datastructures import MutableHeaders

from api.pages import result_page
from apps.accounts.throttle import account_posts

_MAX_BODY = 4096
_BODY_LIMITED = {
    "/api/users",
    "/api/users/verify-email",
    "/api/session",
    "/api/session/logout",
}
_ACCOUNT_LIMITED = {"/api/users", "/api/users/verify-email"}
_TOO_MANY = "Demasiados intentos. Prueba de nuevo en unos minutos."
_TOO_LARGE = "La solicitud es demasiado grande."
_SECURITY_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": (
        "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
}

Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]


def clear_account_limits() -> None:
    account_posts.clear()


def _header(scope: Scope, name: bytes) -> str:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return ""


def _normalized_path(path: str) -> str:
    if len(path) > 1 and path.endswith("/"):
        return path.rstrip("/")
    return path


def _client_host(scope: Scope) -> str:
    client = scope.get("client")
    return client[0] if client else "-"


def _client_key(scope: Scope) -> str:
    return f"{_client_host(scope)} {_normalized_path(scope.get('path', ''))}"


def _allow_post(key: str) -> bool:
    return account_posts.allow(
        key,
        settings.ACCOUNT_POST_LIMIT,
        settings.ACCOUNT_POST_WINDOW_SECONDS,
    )


class _ClientGone(Exception):
    pass


async def _read_body(receive: Receive, limit: int) -> bytes | None:
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            raise _ClientGone
        if message["type"] != "http.request":
            continue
        piece = message.get("body", b"")
        size += len(piece)
        if size > limit:
            return None
        chunks.append(piece)
        if not message.get("more_body", False):
            return b"".join(chunks)


def _error_field(path: str) -> str:
    normalized = _normalized_path(path)
    if normalized.endswith("verify-email"):
        return "token"
    if normalized.startswith("/api/session"):
        return "credentials"
    return "email"


async def _reject(send: Send, scope: Scope, status: int, message: str) -> None:
    field = _error_field(scope.get("path", ""))
    content_type = _header(scope, b"content-type")
    if scope.get("path", "").endswith("verify-email") and "application/json" not in content_type:
        body = result_page(message).encode()
        media = b"text/html; charset=utf-8"
    else:
        body = json.dumps({"errors": {field: [message]}}).encode()
        media = b"application/json"
    headers = [(b"content-type", media), (b"content-length", str(len(body)).encode())]
    for key, value in _SECURITY_HEADERS.items():
        headers.append((key.encode("latin-1"), value.encode("latin-1")))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class AccountGuard:
    """Limits account posts and keeps confirmation pages out of caches and referrers."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = _normalized_path(scope.get("path", ""))
        if path == "/api/docs" or path.startswith("/api/docs/"):
            await self.app(scope, receive, send)
            return

        async def send_hardened(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in _SECURITY_HEADERS.items():
                    headers[key] = value
            await send(message)

        if scope.get("method") != "POST" or path not in _BODY_LIMITED:
            await self.app(scope, receive, send_hardened)
            return

        length = _header(scope, b"content-length")
        if len(length) > 8 or (length.isdigit() and int(length) > _MAX_BODY):
            await _reject(send, scope, 413, _TOO_LARGE)
            return
        if path in _ACCOUNT_LIMITED and not _allow_post(_client_key(scope)):
            await _reject(send, scope, 429, _TOO_MANY)
            return

        try:
            body = await _read_body(receive, _MAX_BODY)
        except _ClientGone:
            return
        if body is None:
            await _reject(send, scope, 413, _TOO_LARGE)
            return
        pending: dict | None = {"type": "http.request", "body": body, "more_body": False}

        async def replay() -> dict:
            nonlocal pending
            if pending is not None:
                message = pending
                pending = None
                return message
            return await receive()

        await self.app(scope, replay, send_hardened)
