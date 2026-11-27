"""Rate limits shared across workers through Django's cache.

Each key is a fixed window counter. ``cache.incr`` is atomic, so two workers
cannot both sneak past the limit. A new key does not push anyone else out:
the old global index filled up and then rejected every new player.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable

from django.core.cache import cache

Clock = Callable[[], float]


class SlidingWindow:
    """Counts hits per key inside a fixed window of ``window_seconds``."""

    def __init__(
        self,
        name: str,
        max_keys: int = 4096,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.name = name
        # Kept so existing callers still construct the limiter. Keys expire
        # with the window, so a full table no longer fails closed for everyone.
        self.max_keys = max_keys
        self._clock = clock or time.time

    def clear(self) -> None:
        gen_key = self._gen_key()
        try:
            cache.incr(gen_key)
        except ValueError:
            cache.add(gen_key, 1, timeout=None)
            try:
                cache.incr(gen_key)
            except ValueError:
                cache.set(gen_key, int(self._clock()), timeout=None)

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        if limit <= 0:
            return True
        if not isinstance(key, str) or not key or len(key) > 256:
            key = "-"
        if window_seconds <= 0:
            return True
        slot = int(self._clock() // window_seconds)
        hits_key = self._hits_key(slot, key)
        timeout = max(int(window_seconds) + 1, 2)
        if cache.add(hits_key, 1, timeout=timeout):
            return True
        try:
            count = cache.incr(hits_key)
        except ValueError:
            cache.set(hits_key, 1, timeout=timeout)
            return True
        return int(count) <= limit

    def _gen_key(self) -> str:
        return f"th:{self.name}:gen"

    def _hits_key(self, slot: int, key: str) -> str:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return f"th:{self.name}:{self._generation()}:{slot}:h:{digest}"

    def _generation(self) -> int:
        gen_key = self._gen_key()
        value = cache.get(gen_key)
        if value is None:
            cache.add(gen_key, 1, timeout=None)
            value = cache.get(gen_key)
            if value is None:
                cache.set(gen_key, 1, timeout=None)
                value = 1
        return int(value)


account_posts = SlidingWindow("account_posts")
admin_logins = SlidingWindow("admin_logins")
login_ips = SlidingWindow("login_ips")
login_emails = SlidingWindow("login_emails")


def clear_login_limits() -> None:
    login_ips.clear()
    login_emails.clear()
