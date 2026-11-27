"""Server-sent events for campaign and notification push."""

from __future__ import annotations

import asyncio
import json

from asgiref.sync import sync_to_async
from django.db import close_old_connections
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.player_gate import reader as _reader
from apps.campaigns.live import live_bus

router = APIRouter()

_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.get("/api/events")
async def get_events(request: Request):
    close_old_connections()
    try:
        user = await sync_to_async(_reader, thread_sensitive=True)(request)
    finally:
        close_old_connections()
    if isinstance(user, JSONResponse):
        return user
    user_id = int(user.pk)

    try:
        queue = live_bus.subscribe(user_id)
    except RuntimeError:
        return JSONResponse(
            {"errors": {"form": ["Demasiadas conexiones en vivo. Cierra otras pestañas."]}},
            status_code=429,
        )

    async def stream():
        try:
            yield _frame({"type": "ready"})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield _frame(event)
        finally:
            live_bus.unsubscribe(user_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_HEADERS)


def _frame(event: dict) -> str:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
