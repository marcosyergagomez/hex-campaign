"""Local development against the Docker database."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import DATABASES, SECRET_KEY, SESSION_PEPPER

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required. Copy .env.example to .env.")
if not DATABASES:
    raise ImproperlyConfigured("DATABASE_URL is required. Copy .env.example to .env.")
if len(SESSION_PEPPER) < 50:
    raise ImproperlyConfigured(
        "SESSION_PEPPER must be at least 50 characters. Copy .env.example to .env."
    )
