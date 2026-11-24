"""Slow down password guesses against the admin login."""

from django.conf import settings
from django.http import HttpResponse

from .throttle import admin_logins

_TOO_MANY = "Demasiados intentos. Prueba de nuevo en unos minutos."
_LOGIN_PATH = "/admin/login"


class AdminLoginThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path.rstrip("/") == _LOGIN_PATH:
            username = (request.POST.get("username") or "").strip().lower()[:254]
            key = username or (request.META.get("REMOTE_ADDR") or "-")
            if not admin_logins.allow(
                key,
                settings.ADMIN_LOGIN_LIMIT,
                settings.ADMIN_LOGIN_WINDOW_SECONDS,
            ):
                return HttpResponse(
                    _TOO_MANY,
                    status=429,
                    content_type="text/plain; charset=utf-8",
                )
        return self.get_response(request)
