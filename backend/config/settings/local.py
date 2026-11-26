"""Local development against the Docker database."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import DATABASES, REPO_ROOT, SECRET_KEY, SESSION_PEPPER

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

# Prefer the repo .env over a polluted shell (e.g. pytest leftovers), so local
# login and writes keep matching the Vite origin.
_env_path = Path(REPO_ROOT) / ".env"
if _env_path.is_file():
    for raw_line in _env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "API_ORIGIN":
            API_ORIGIN = value.strip().strip('"').strip("'").rstrip("/")
            os.environ["API_ORIGIN"] = API_ORIGIN
            break
