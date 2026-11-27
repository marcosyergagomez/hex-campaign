"""Production flags. Deployments must set the secret, the database, and the hosts."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import CACHE_URL, DATABASES, SECRET_KEY, SESSION_PEPPER, TRUST_PROXY, cache_from_url
from .guards import require_https_origin, require_secret, require_session_pepper

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

require_secret(SECRET_KEY)
require_session_pepper(SESSION_PEPPER)
if not DATABASES:
    raise ImproperlyConfigured("DATABASE_URL is required.")
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 5
if not CACHE_URL:
    raise ImproperlyConfigured("CACHE_URL is required (redis://… for shared rate limits).")
CACHES = {"default": cache_from_url(CACHE_URL)}

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("ALLOWED_HOSTS", "").split(",") if host.strip()
]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS is required.")
if not os.environ.get("EMAIL_HOST"):
    raise ImproperlyConfigured("EMAIL_HOST is required.")
if not os.environ.get("DEFAULT_FROM_EMAIL"):
    raise ImproperlyConfigured("DEFAULT_FROM_EMAIL is required.")
API_ORIGIN = require_https_origin(os.environ.get("API_ORIGIN"))
if TRUST_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
