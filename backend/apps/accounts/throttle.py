"""Rate limits shared across workers through Django's cache.

LocMem is fine for a single process. Production sets CACHE_URL to Redis so
every uvicorn worker sees the same counters.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable

from django.core.cache import cache

Clock = Callable[[], float]


class SlidingWindow:
    """Counts hits per key. A full index rejects new keys instead of dropping old ones."""

    def __init__(
        self,
        name: str,
        max_keys: int = 4096,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.name = name
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
        now = self._clock()
        gen = self._generation()
        hits_key = self._hits_key(gen, key)
        index_key = f"th:{self.name}:{gen}:i"
        timeout = max(int(window_seconds) + 1, 2)
        cutoff = now - window_seconds

        hits = [stamp for stamp in (cache.get(hits_key) or ()) if stamp >= cutoff]
        if len(hits) >= limit:
            cache.set(hits_key, hits, timeout=timeout)
            return False

        index = list(cache.get(index_key) or ())
        if key not in index:
            alive: list[str] = []
            for name in index:
                other_key = self._hits_key(gen, name)
                other = [stamp for stamp in (cache.get(other_key) or ()) if stamp >= cutoff]
                if other:
                    alive.append(name)
                    cache.set(other_key, other, timeout=timeout)
                else:
                    cache.delete(other_key)
            index = alive
            if len(index) >= self.max_keys:
                cache.set(index_key, index, timeout=timeout)
                return False
            index.append(key)
            cache.set(index_key, index, timeout=timeout)

        hits.append(now)
        cache.set(hits_key, hits, timeout=timeout)
        return True

    def _gen_key(self) -> str:
        return f"th:{self.name}:gen"

    def _hits_key(self, gen: int, key: str) -> str:
        # Paths and spaces are hashed so Redis and memcached accept the key.
        digest = hashlib.sha256(key.encode()).hexdigest()
        return f"th:{self.name}:{gen}:h:{digest}"

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
