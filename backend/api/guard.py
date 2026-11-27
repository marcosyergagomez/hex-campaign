"""Bounds and response headers for the public API.

The confirmation page carries a secret in the query string, so responses are
not cached and do not send a referrer. Account posts stay small. A campaign
post may carry an army list, so its cap is higher, and it never reaches the
password hasher.
"""

import json
import logging
from collections.abc import Awaitable, Callable

from django.conf import settings
from starlette.datastructures import MutableHeaders

from api.client_address import client_address
from api.pages import result_page
from apps.accounts.throttle import account_posts

_ACCOUNT_BODY = 4096
# Campaign create may carry a 15000-char lore blurb plus rules JSON.
_CAMPAIGN_BODY = 65536
# Drawn maps send every hex, including previously saved 817-cell boards.
_MAP_BODY = 98304
_BODY_LIMITED = {
    "/api/users",
    "/api/users/verify-email",
    "/api/session",
    "/api/session/logout",
    "/api/profile",
    "/api/password-reset",
    "/api/password-reset/confirm",
}
# Auth signup/confirm stay tightly capped. Gameplay posts (roads, orders) are
# frequent, so they use a separate higher ceiling instead of the account budget.
_ACCOUNT_LIMITED = {
    "/api/users",
    "/api/users/verify-email",
    "/api/profile",
    "/api/password-reset",
    "/api/password-reset/confirm",
}
_PLAY_PREFIXES = ("/api/campaigns", "/api/maps", "/api/invitations")
_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_TOO_MANY = "Demasiados intentos. Prueba de nuevo en unos minutos."
_TOO_LARGE = "La solicitud es demasiado grande."
log = logging.getLogger("hexcampaign.http")

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


def _client_key(scope: Scope) -> str:
    return f"{client_address(scope)} {_normalized_path(scope.get('path', ''))}"


def _allow_post(key: str, *, limit: int, window: int) -> bool:
    return account_posts.allow(key, limit, window)


def _rate_limit(path: str) -> tuple[int, int] | None:
    if path in _ACCOUNT_LIMITED:
        return settings.ACCOUNT_POST_LIMIT, settings.ACCOUNT_POST_WINDOW_SECONDS
    if any(path == prefix or path.startswith(prefix + "/") for prefix in _PLAY_PREFIXES):
        return settings.PLAY_POST_LIMIT, settings.PLAY_POST_WINDOW_SECONDS
    return None


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
    if normalized.startswith("/api/profile"):
        return "alias"
    if normalized.startswith(("/api/campaigns", "/api/invitations")):
        return "campaign"
    if normalized.startswith("/api/maps"):
        return "map"
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


def _body_limit(path: str) -> int | None:
    if path in _BODY_LIMITED:
        return _ACCOUNT_BODY
    if path.startswith(("/api/campaigns", "/api/invitations")):
        return _CAMPAIGN_BODY
    if path.startswith("/api/maps"):
        return _MAP_BODY
    return None


class AccountGuard:
    """Limits posts and keeps confirmation pages out of caches and referrers."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self._http(scope, receive, send)
        except Exception:
            log.exception(
                "api request failed method=%s path=%s",
                scope.get("method", ""),
                _normalized_path(str(scope.get("path", ""))),
            )
            raise

    async def _http(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = _normalized_path(scope.get("path", ""))
        if path == "/api/docs" or path.startswith("/api/docs/"):
            await self.app(scope, receive, send)
            return

        async def send_hardened(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in _SECURITY_HEADERS.items():
                    headers[key] = value
                if not settings.DEBUG:
                    headers["strict-transport-security"] = (
                        "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        method = scope.get("method", "")
        if method in _MUTATING:
            budget = _rate_limit(path)
            if budget is not None and not _allow_post(
                _client_key(scope), limit=budget[0], window=budget[1]
            ):
                log.warning("request rejected status=429 path=%s", path)
                await _reject(send, scope, 429, _TOO_MANY)
                return

        limit = _body_limit(path)
        if method not in {"POST", "PUT", "PATCH"} or limit is None:
            await self.app(scope, receive, send_hardened)
            return

        length = _header(scope, b"content-length")
        if len(length) > 8 or (length.isdigit() and int(length) > limit):
            log.warning("request rejected status=413 path=%s", path)
            await _reject(send, scope, 413, _TOO_LARGE)
            return

        try:
            body = await _read_body(receive, limit)
        except _ClientGone:
            return
        if body is None:
            log.warning("request rejected status=413 path=%s", path)
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
