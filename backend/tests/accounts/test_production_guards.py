"""Production refuses a weak secret and a confirmation link that is not https."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.guards import (
    LOCAL_SESSION_PEPPER,
    require_https_origin,
    require_secret,
    require_session_pepper,
)


def test_production_requires_a_long_unique_secret() -> None:
    with pytest.raises(ImproperlyConfigured):
        require_secret(None)
    with pytest.raises(ImproperlyConfigured):
        require_secret("short")
    with pytest.raises(ImproperlyConfigured):
        require_secret("change-me-before-any-shared-environment")
    with pytest.raises(ImproperlyConfigured):
        require_secret("x" * 49)

    require_secret("x" * 50)


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "",
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/api",
        "https://example.com?token=1",
        "https://example.com#frag",
        "https://exam\nple.com",
        "https://example.com extra",
    ],
)
def test_production_rejects_a_confirmation_origin_that_is_not_https(origin: str | None) -> None:
    with pytest.raises(ImproperlyConfigured):
        require_https_origin(origin)


def test_production_rejects_a_shared_session_pepper() -> None:
    with pytest.raises(ImproperlyConfigured):
        require_session_pepper(None)
    with pytest.raises(ImproperlyConfigured):
        require_session_pepper("short")
    with pytest.raises(ImproperlyConfigured):
        require_session_pepper("change-me-before-any-shared-environment")
    with pytest.raises(ImproperlyConfigured):
        require_session_pepper(LOCAL_SESSION_PEPPER)

    require_session_pepper("p" * 50)


def test_production_accepts_an_https_origin() -> None:
    assert require_https_origin(" https://example.com/ ") == "https://example.com"
    assert require_https_origin("https://example.com:443") == "https://example.com:443"
