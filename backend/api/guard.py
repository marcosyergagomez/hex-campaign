"""Bounds and response headers for the account routes.

The confirmation page carries a secret in the query string, so responses are
not cached and do not send a referrer. Posts are capped so a large body never
reaches the hasher.
"""

import json
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable

from django.conf import settings
from starlette.datastructures import MutableHeaders

from api.pages import result_page

_MAX_BODY = 4096
_MAX_TRACKED_CLIENTS = 4096
_POST_PATHS = {"/api/users", "/api/users/verify-email"}
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
_LIMIT_LOCK = threading.Lock()
_HITS: dict[str, deque[float]] = {}

Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]


def clear_account_limits() -> None:
    with _LIMIT_LOCK:
        _HITS.clear()


def _header(scope: Scope, name: bytes) -> str:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return ""


def _client_key(scope: Scope) -> str:
    client = scope.get("client")
    host = client[0] if client else "-"
    return f"{host} {scope.get('path', '')}"


def _allow_post(key: str) -> bool:
    limit = settings.ACCOUNT_POST_LIMIT
    window = settings.ACCOUNT_POST_WINDOW_SECONDS
    if limit <= 0:
        return True
    now = time.monotonic()
    with _LIMIT_LOCK:
        if key not in _HITS and len(_HITS) >= _MAX_TRACKED_CLIENTS:
            _HITS.pop(next(iter(_HITS)))
        hits = _HITS.setdefault(key, deque())
        cutoff = now - window
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


async def _read_body(receive: Receive, limit: int) -> bytes | None:
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return b"".join(chunks)
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
    if path.endswith("verify-email"):
        return "token"
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

        path = scope.get("path", "")
        if path == "/api/docs" or path.startswith("/api/docs/"):
            await self.app(scope, receive, send)
            return

        async def send_hardened(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in _SECURITY_HEADERS.items():
                    headers[key] = value
            await send(message)

        if scope.get("method") != "POST" or path not in _POST_PATHS:
            await self.app(scope, receive, send_hardened)
            return

        length = _header(scope, b"content-length")
        if len(length) > 8 or (length.isdigit() and int(length) > _MAX_BODY):
            await _reject(send, scope, 413, _TOO_LARGE)
            return
        if not _allow_post(_client_key(scope)):
            await _reject(send, scope, 429, _TOO_MANY)
            return

        body = await _read_body(receive, _MAX_BODY)
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
