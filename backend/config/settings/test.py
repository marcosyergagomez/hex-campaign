"""Tests use the local Docker Postgres and create their own database."""

import os

from .base import *  # noqa: F403
from .base import database_from_url

DEBUG = False
SECRET_KEY = "test-only-secret-key-not-used-outside-pytest"
ALLOWED_HOSTS = ["localhost", "testserver"]
DATABASES = {
    "default": database_from_url(
        os.environ.get(
            "DATABASE_URL",
            "postgres://hexcampaign:hexcampaign@localhost:5432/hexcampaign",
        )
    )
}
# Process-local cache keeps pytest free of Redis while still exercising the API.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "hexcampaign-test-throttle",
    }
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
API_ORIGIN = "http://testserver"
SESSION_PEPPER = "test-only-session-pepper-not-used-outside-pytest-0123456789"
ACCOUNT_POST_LIMIT = 10_000
PLAY_POST_LIMIT = 10_000
LOGIN_IP_LIMIT = 10_000
LOGIN_EMAIL_LIMIT = 10_000
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "api.request_id.RequestIdFilter"},
    },
    "formatters": {
        "plain": {"()": "api.request_id.RequestIdFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}
