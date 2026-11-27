"""Shared settings. Secrets and the database URL come from the environment."""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BASE_DIR.parent


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines without overriding variables already set."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def database_from_url(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.path.strip("/"):
        raise RuntimeError("DATABASE_URL must be a postgres URL with a database name.")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.strip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or 5432),
    }


def cache_from_url(url: str) -> dict[str, object]:
    """Redis URL for a cache shared by every worker. LocMem stays process-local."""
    parsed = urlparse(url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise RuntimeError("CACHE_URL must be a redis:// or rediss:// URL.")
    return {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": url,
        "KEY_PREFIX": "hexcampaign",
    }


load_env_file(REPO_ROOT / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DATABASES = {"default": database_from_url(DATABASE_URL)} if DATABASE_URL else {}
CACHE_URL = os.environ.get("CACHE_URL", "").strip()
if CACHE_URL:
    CACHES = {"default": cache_from_url(CACHE_URL)}
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "hexcampaign-throttle",
        }
    }

DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.campaigns",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.accounts.middleware.AdminLoginThrottleMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


def _env_flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes"}


EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _env_flag("EMAIL_USE_TLS")
EMAIL_USE_SSL = _env_flag("EMAIL_USE_SSL")
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@localhost")
API_ORIGIN = os.environ.get("API_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
# HMAC key for player-session cookies. A database copy without this is not a login.
SESSION_PEPPER = os.environ.get("SESSION_PEPPER", "")
# The campaign can last for months. The cookie does not: 60 days idle, 180 absolute.
SESSION_IDLE_SECONDS = 60 * 60 * 24 * 60
SESSION_ABSOLUTE_SECONDS = 60 * 60 * 24 * 180
SESSION_TOUCH_SECONDS = 60 * 60
SESSION_MAX_PER_USER = 10
LOGIN_IP_LIMIT = int(os.environ.get("LOGIN_IP_LIMIT", "10"))
LOGIN_IP_WINDOW_SECONDS = int(os.environ.get("LOGIN_IP_WINDOW_SECONDS", "900"))
LOGIN_EMAIL_LIMIT = int(os.environ.get("LOGIN_EMAIL_LIMIT", "10"))
LOGIN_EMAIL_WINDOW_SECONDS = int(os.environ.get("LOGIN_EMAIL_WINDOW_SECONDS", "900"))
ACCOUNT_POST_LIMIT = int(os.environ.get("ACCOUNT_POST_LIMIT", "30"))
ACCOUNT_POST_WINDOW_SECONDS = int(os.environ.get("ACCOUNT_POST_WINDOW_SECONDS", "60"))
# Road painting and order locks need more headroom than account signup.
PLAY_POST_LIMIT = int(os.environ.get("PLAY_POST_LIMIT", "180"))
PLAY_POST_WINDOW_SECONDS = int(os.environ.get("PLAY_POST_WINDOW_SECONDS", "60"))
ADMIN_LOGIN_LIMIT = int(os.environ.get("ADMIN_LOGIN_LIMIT", "20"))
ADMIN_LOGIN_WINDOW_SECONDS = int(os.environ.get("ADMIN_LOGIN_WINDOW_SECONDS", "900"))
# Turn on only behind a proxy that appends the real client to X-Forwarded-For
# and overwrites X-Forwarded-Proto. A browser-supplied value is then not last.
TRUST_PROXY = _env_flag("TRUST_PROXY")

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = False

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
    "root": {"handlers": ["console"], "level": "INFO"},
}
