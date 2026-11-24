"""In-memory sliding windows for account posts and the admin login."""

import threading
import time
from collections import deque


class SlidingWindow:
    """Counts hits per key. A full table rejects new keys instead of forgetting old ones."""

    def __init__(self, max_keys: int = 4096) -> None:
        self._max_keys = max_keys
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            cutoff = now - window_seconds
            if key not in self._hits and len(self._hits) >= self._max_keys:
                stale = [
                    name
                    for name, hits in self._hits.items()
                    if not hits or hits[-1] < cutoff
                ]
                for name in stale:
                    del self._hits[name]
                if key not in self._hits and len(self._hits) >= self._max_keys:
                    return False
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


account_posts = SlidingWindow()
admin_logins = SlidingWindow()
