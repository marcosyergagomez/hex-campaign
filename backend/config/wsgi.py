"""WSGI entrypoint."""

import os

from django.core.wsgi import get_wsgi_application

if "DJANGO_SETTINGS_MODULE" not in os.environ:
    if os.environ.get("APP_ENV") == "production":
        raise RuntimeError("DJANGO_SETTINGS_MODULE must be set when APP_ENV=production")
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"

application = get_wsgi_application()
