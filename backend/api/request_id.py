"""One id per HTTP request, carried into every log line."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, cast

from starlette.datastructures import MutableHeaders

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
HEADER = "x-request-id"

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]

log = logging.getLogger("hexcampaign.http")


def current_request_id() -> str:
    return request_id_var.get()


def _incoming(scope: Scope) -> str:
    headers = scope.get("headers", [])
    if isinstance(headers, list):
        for item in headers:
            if not (isinstance(item, tuple) and len(item) == 2):
                continue
            key, value = item
            if key != b"x-request-id":
                continue
            if not isinstance(value, bytes):
                break
            raw = value.decode("latin-1", errors="replace").strip()
            if _REQUEST_ID.fullmatch(raw):
                return raw
            break
    return uuid.uuid4().hex


class _Stamped(logging.LogRecord):
    request_id: str


class RequestIdFilter(logging.Filter):
    """Stamp the id while the request is still running."""

    def filter(self, record: logging.LogRecord) -> bool:
        cast(_Stamped, record).request_id = current_request_id()
        return True


class RequestIdFormatter(logging.Formatter):
    """key=value line so every backend log carries the current request id."""

    def __init__(self) -> None:
        super().__init__(
            "%(asctime)s level=%(levelname)s logger=%(name)s request_id=%(request_id)s %(message)s"
        )

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            cast(_Stamped, record).request_id = current_request_id()
        return super().format(record)


class RequestIdMiddleware:
    """Read X-Request-ID or mint one, then return it on the response."""

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = _incoming(scope)
        scope["hexcampaign.request_id"] = request_id
        token = request_id_var.set(request_id)

        async def send_with_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[HEADER] = request_id
            await send(message)

        try:
            log.debug("http request")
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
