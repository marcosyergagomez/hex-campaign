"""Production flags. Deployments must set the secret, the database, and the hosts."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import DATABASES, SECRET_KEY

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required.")
if not DATABASES:
    raise ImproperlyConfigured("DATABASE_URL is required.")

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("ALLOWED_HOSTS", "").split(",") if host.strip()
]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS is required.")
if not os.environ.get("EMAIL_HOST"):
    raise ImproperlyConfigured("EMAIL_HOST is required.")
if not os.environ.get("DEFAULT_FROM_EMAIL"):
    raise ImproperlyConfigured("DEFAULT_FROM_EMAIL is required.")
if not os.environ.get("API_ORIGIN"):
    raise ImproperlyConfigured("API_ORIGIN is required.")
