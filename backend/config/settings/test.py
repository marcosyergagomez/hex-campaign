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
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
API_ORIGIN = "http://testserver"
