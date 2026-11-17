"""Local development against the Docker database."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import DATABASES, SECRET_KEY

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required. Copy .env.example to .env.")
if not DATABASES:
    raise ImproperlyConfigured("DATABASE_URL is required. Copy .env.example to .env.")
