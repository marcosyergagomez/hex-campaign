"""ASGI entrypoint. Django serves the admin and FastAPI serves /api."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")


def _applications():
    django_application = get_asgi_application()
    from api.app import api

    return django_application, api


django_application, api = _applications()


async def application(scope, receive, send):
    if scope["type"] == "lifespan":
        await _lifespan(receive, send)
        return
    if scope["type"] == "http" and scope.get("path", "").startswith("/api"):
        await api(scope, receive, send)
        return
    await django_application(scope, receive, send)


async def _lifespan(receive, send):
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return
