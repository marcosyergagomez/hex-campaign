"""Account posts and the admin login share a fail-closed counter."""

import pytest
from django.contrib.auth.models import Group

from apps.accounts.models import User
from apps.accounts.registration import RegistrationError
from apps.accounts.throttle import SlidingWindow, admin_logins
from tests.accounts.test_registration_service import PASSWORD, _register


def test_a_full_window_rejects_a_new_key_and_keeps_the_old_count() -> None:
    window = SlidingWindow(max_keys=2)

    assert window.allow("a", limit=2, window_seconds=60) is True
    assert window.allow("b", limit=2, window_seconds=60) is True
    assert window.allow("c", limit=2, window_seconds=60) is False
    assert window.allow("a", limit=2, window_seconds=60) is True
    assert window.allow("a", limit=2, window_seconds=60) is False


def test_expired_keys_leave_room_for_a_new_client() -> None:
    window = SlidingWindow(max_keys=1)
    assert window.allow("a", limit=1, window_seconds=60) is True

    window._hits["a"][0] -= 120

    assert window.allow("b", limit=1, window_seconds=60) is True


def test_a_disabled_limit_always_allows() -> None:
    window = SlidingWindow(max_keys=1)
    assert window.allow("a", limit=1, window_seconds=60) is True
    assert window.allow("b", limit=0, window_seconds=60) is True


@pytest.mark.django_db
def test_admin_login_guesses_are_limited_per_account(client, settings) -> None:
    admin_logins.clear()
    settings.ADMIN_LOGIN_LIMIT = 1
    settings.ADMIN_LOGIN_WINDOW_SECONDS = 60

    first = client.post("/admin/login/", {"username": "Admin@Example.com", "password": "no"})
    second = client.post("/admin/login/", {"username": "admin@example.com", "password": "otra"})
    other = client.post("/admin/login/", {"username": "otra@example.com", "password": "no"})
    admin_logins.clear()

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Demasiados intentos" in second.content.decode()
    assert other.status_code == 200


@pytest.mark.django_db
def test_a_grouped_account_is_not_replaced(mailoutbox) -> None:
    _register()
    user = User.objects.get()
    user.groups.add(Group.objects.create(name="editores"))

    with pytest.raises(RegistrationError) as taken:
        _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")

    assert taken.value.errors == {"email": ["Este correo ya está registrado."]}
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    assert user.alias == "ada_lovelace"
    assert len(mailoutbox) == 1
