"""Client address for rate limits.

The socket peer is the client unless TRUST_PROXY is on. Then the last
X-Forwarded-For hop is used: that is the address the trusted proxy appended.
A value the browser invented sits further left and is ignored.
"""

from collections.abc import Mapping
from typing import Any

from django.conf import settings


def client_address(scope: Mapping[str, Any]) -> str:
    peer = _peer(scope)
    if not getattr(settings, "TRUST_PROXY", False):
        return peer
    forwarded = _header(scope, b"x-forwarded-for")
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    if not parts:
        return peer
    chosen = parts[-1]
    if len(chosen) > 64 or any(ord(char) < 33 or ord(char) == 127 for char in chosen):
        return peer
    return chosen


def _peer(scope: Mapping[str, Any]) -> str:
    client = scope.get("client")
    if isinstance(client, tuple) and client and isinstance(client[0], str) and client[0]:
        return client[0]
    return "-"


def _header(scope: Mapping[str, Any], name: bytes) -> str:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return ""
