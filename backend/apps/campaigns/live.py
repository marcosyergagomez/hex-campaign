"""Push bus for logged-in players.

One process keeps subscriber queues in memory. When the cache is Redis, every
worker publishes on one channel and its own listener delivers to local queues.
Without Redis, delivery stays in this process. A Redis error is logged and
this process still delivers to its own subscribers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any

CHANNEL = "hexcampaign:live"
_CONNECT_TIMEOUT = 2.0
_PUBLISH_TIMEOUT = 2.0

log = logging.getLogger("hexcampaign.live")


def _redis_location() -> str | None:
    from django.conf import settings

    cache = settings.CACHES.get("default", {})
    if cache.get("BACKEND") != "django.core.cache.backends.redis.RedisCache":
        return None
    location = cache.get("LOCATION")
    if isinstance(location, str) and location.startswith(("redis://", "rediss://")):
        return location
    return None


class LiveBus:
    # Soft cap per signed-in user so a leaked session cannot open unbounded SSE fans.
    MAX_SUBSCRIPTIONS = 3

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs: dict[int, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._listener_started = False
        self._publisher: Any = None

    def start(self) -> None:
        url = _redis_location()
        if not url:
            return
        with self._lock:
            if self._listener_started:
                return
            self._listener_started = True
        threading.Thread(
            target=self._listen,
            args=(url,),
            name="hexcampaign-live",
            daemon=True,
        ).start()

    def subscribe(self, user_id: int) -> asyncio.Queue[dict[str, Any]]:
        self.start()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        with self._lock:
            holders = self._subs.setdefault(user_id, set())
            if len(holders) >= self.MAX_SUBSCRIPTIONS:
                raise RuntimeError("too_many_streams")
            self._loop = asyncio.get_running_loop()
            holders.add(queue)
        return queue

    def unsubscribe(self, user_id: int, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            holders = self._subs.get(user_id)
            if holders is None:
                return
            holders.discard(queue)
            if not holders:
                self._subs.pop(user_id, None)

    def publish_users(
        self,
        user_ids: list[int] | set[int] | tuple[int, ...],
        event: dict[str, Any],
    ) -> None:
        ids = [int(user_id) for user_id in user_ids]
        if not ids:
            return
        url = _redis_location()
        if url:
            self.start()
            try:
                self._publish_redis(url, ids, event)
                return
            except Exception:
                with self._lock:
                    self._publisher = None
                log.error(
                    "redis publish failed; delivering in this process recipients=%s",
                    len(ids),
                    exc_info=True,
                )
        self._deliver_local(ids, event)

    def _publish_redis(self, url: str, user_ids: list[int], event: dict[str, Any]) -> None:
        import redis

        with self._lock:
            publisher = self._publisher
            if publisher is None:
                publisher = redis.Redis.from_url(
                    url,
                    socket_connect_timeout=_CONNECT_TIMEOUT,
                    socket_timeout=_PUBLISH_TIMEOUT,
                )
                self._publisher = publisher
        publisher.publish(
            CHANNEL,
            json.dumps({"user_ids": user_ids, "event": event}, separators=(",", ":")),
        )

    def _listen(self, url: str) -> None:
        import redis

        failures = 0
        while True:
            try:
                client = redis.Redis.from_url(
                    url,
                    socket_connect_timeout=_CONNECT_TIMEOUT,
                    socket_timeout=None,
                )
                pubsub = client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(CHANNEL)
                if failures:
                    log.info("live listener restored")
                else:
                    log.info("live listener subscribed")
                failures = 0
                for message in pubsub.listen():
                    if not isinstance(message, dict) or message.get("type") != "message":
                        continue
                    raw = message.get("data")
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    if not isinstance(raw, str):
                        continue
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    user_ids = payload.get("user_ids")
                    event = payload.get("event")
                    if not isinstance(user_ids, list) or not isinstance(event, dict):
                        continue
                    self._deliver_local(user_ids, event)
            except Exception:  # noqa: BLE001 - the listener must survive any client failure
                failures += 1
                self._note_listen_failure(failures)
                time.sleep(1)

    def _note_listen_failure(self, failures: int) -> None:
        if failures != 1 and failures % 30 != 0:
            return
        log.error(
            "redis subscription dropped; retrying failure=%s",
            failures,
            exc_info=True,  # noqa: LOG014 - called from the listener's except
        )

    def _deliver_local(self, user_ids: list[int], event: dict[str, Any]) -> None:
        ids = {int(user_id) for user_id in user_ids}
        with self._lock:
            loop = self._loop
            targets: list[asyncio.Queue[dict[str, Any]]] = []
            for user_id in ids:
                targets.extend(self._subs.get(user_id, ()))
        if loop is None or not targets:
            return

        def deliver() -> None:
            for queue in targets:
                _offer(queue, event)

        try:
            loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            log.warning("live delivery skipped because the event loop is closed")


def _offer(queue: asyncio.Queue[dict[str, Any]], event: dict[str, Any]) -> None:
    try:
        queue.put_nowait(event)
        return
    except asyncio.QueueFull:
        pass
    try:
        while True:
            queue.get_nowait()
    except asyncio.QueueEmpty:
        pass
    try:
        # The dropped events are gone. Ask the client to reload instead of guessing.
        queue.put_nowait({"type": "reconnect"})
    except asyncio.QueueFull:
        pass


live_bus = LiveBus()
