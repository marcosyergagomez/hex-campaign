"""In-process push bus for logged-in players.

One uvicorn worker keeps subscriber queues in memory. Multi-worker deploys need a
shared broker later; until then this avoids constant polling.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any


class LiveBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs: dict[int, set[asyncio.Queue[dict[str, Any]]]] = {}

    def subscribe(self, user_id: int) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._subs.setdefault(user_id, set()).add(queue)
        return queue

    def unsubscribe(self, user_id: int, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            holders = self._subs.get(user_id)
            if holders is None:
                return
            holders.discard(queue)
            if not holders:
                self._subs.pop(user_id, None)

    def publish_users(self, user_ids: list[int] | set[int] | tuple[int, ...], event: dict[str, Any]) -> None:
        ids = {int(user_id) for user_id in user_ids}
        if not ids:
            return
        with self._lock:
            loop = self._loop
            targets: list[asyncio.Queue[dict[str, Any]]] = []
            for user_id in ids:
                targets.extend(self._subs.get(user_id, ()))
        if loop is None or not targets:
            return

        def deliver() -> None:
            for queue in targets:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        pass

        try:
            loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            pass


live_bus = LiveBus()
