"""Production checks for the secret and the public origin of confirmation links."""

from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

_PLACEHOLDER_SECRET = "change-me-before-any-shared-environment"


def require_secret(secret: str | None) -> None:
    if not secret or secret == _PLACEHOLDER_SECRET or len(secret) < 50:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be a unique secret of at least 50 characters."
        )


def require_https_origin(origin: str | None) -> str:
    if origin is None:
        raise ImproperlyConfigured("API_ORIGIN is required.")
    cleaned = origin.strip().rstrip("/")
    if not cleaned or any(ord(char) < 32 or char == " " for char in cleaned):
        raise ImproperlyConfigured("API_ORIGIN must be an https origin.")
    parsed = urlsplit(cleaned)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path
    ):
        raise ImproperlyConfigured("API_ORIGIN must be an https origin.")
    return cleaned
