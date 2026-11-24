"""Player sessions are revocable records, not campaign data."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import PlayerSession, User
from apps.accounts.sessions import (
    LoginRejected,
    LoginThrottled,
    csrf_matches,
    load_session,
    login,
    session_digest,
)
from apps.accounts.throttle import clear_login_limits

PASSWORD = "una-clave-larga"


@pytest.fixture(autouse=True)
def _reset_login_limits():
    clear_login_limits()
    yield
    clear_login_limits()


def _player(
    email: str = "ada@example.com",
    password: str = PASSWORD,
    *,
    alias: str = "ada_lovelace",
    verified: bool = True,
    active: bool = True,
    staff: bool = False,
) -> User:
    user = User.objects.create_user(
        email,
        password,
        alias=alias,
        birth_date=date(1990, 1, 1),
        sex="woman",
        is_active=active,
        is_staff=staff,
    )
    if verified:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


@pytest.mark.django_db
def test_login_stores_an_hmac_and_not_the_cookie() -> None:
    _player()

    opened = login(" Ada@Example.com ", PASSWORD)
    row = PlayerSession.objects.get()

    assert opened.user.alias == "ada_lovelace"
    assert row.token_hash == session_digest(opened.token, purpose="session")
    assert row.token_hash != opened.token
    assert row.csrf_hash == session_digest(opened.csrf_token, purpose="csrf")
    assert session_digest(opened.token, purpose="session") != session_digest(
        opened.token, purpose="csrf"
    )
    assert csrf_matches(row, opened.csrf_token, opened.csrf_token)
    assert not csrf_matches(row, opened.csrf_token, opened.token)
    loaded = load_session(opened.token)
    assert loaded is not None and loaded.pk == row.pk


@pytest.mark.django_db
def test_rejected_logins_do_not_open_a_session(monkeypatch: pytest.MonkeyPatch) -> None:
    _player()
    _player(email="quiet@example.com", alias="quiet_user", verified=False)
    _player(email="off@example.com", alias="off_user", active=False)

    with pytest.raises(LoginRejected):
        login("nadie@example.com", PASSWORD)
    with pytest.raises(LoginRejected):
        login("ada@example.com", "clave-equivocada")
    with pytest.raises(LoginRejected):
        login("quiet@example.com", PASSWORD)
    with pytest.raises(LoginRejected):
        login("off@example.com", PASSWORD)

    assert PlayerSession.objects.count() == 0

    def fail(password: str, encoded: str) -> bool:
        raise AssertionError(password)

    monkeypatch.setattr("apps.accounts.sessions.check_user_password", fail)
    monkeypatch.setattr("apps.accounts.sessions.check_encoded_password", fail)
    with pytest.raises(LoginRejected):
        login("ada@example.com", "a" * 129)


@pytest.mark.django_db
def test_spaces_in_the_password_are_part_of_the_secret() -> None:
    password = "  una-clave-larga  "
    _player(password=password)

    with pytest.raises(LoginRejected):
        login("ada@example.com", password.strip())

    assert login("ada@example.com", password).user.email == "ada@example.com"


@pytest.mark.django_db
def test_a_staff_player_can_sign_in() -> None:
    _player(staff=True)

    assert login("ada@example.com", PASSWORD).user.is_staff is True


@pytest.mark.django_db
def test_idle_and_absolute_expiry_drop_the_row(settings) -> None:
    settings.SESSION_IDLE_SECONDS = 60
    settings.SESSION_ABSOLUTE_SECONDS = 3600
    _player()
    opened = login("ada@example.com", PASSWORD)
    row = PlayerSession.objects.get()
    row.last_seen_at = timezone.now() - timedelta(seconds=61)
    row.save(update_fields=["last_seen_at"])

    assert load_session(opened.token) is None
    assert PlayerSession.objects.count() == 0

    again = login("ada@example.com", PASSWORD)
    row = PlayerSession.objects.get()
    row.expires_at = timezone.now() - timedelta(seconds=1)
    row.save(update_fields=["expires_at"])

    assert load_session(again.token) is None
    assert PlayerSession.objects.count() == 0


@pytest.mark.django_db
def test_a_recent_visit_is_not_written_again(settings) -> None:
    settings.SESSION_TOUCH_SECONDS = 3600
    _player()
    opened = login("ada@example.com", PASSWORD)
    seen = PlayerSession.objects.get().last_seen_at

    assert load_session(opened.token) is not None
    assert PlayerSession.objects.get().last_seen_at == seen

    PlayerSession.objects.update(last_seen_at=timezone.now() - timedelta(hours=2))
    assert load_session(opened.token) is not None
    assert PlayerSession.objects.get().last_seen_at > seen


@pytest.mark.django_db
def test_the_oldest_session_is_dropped_at_the_cap(settings) -> None:
    settings.SESSION_MAX_PER_USER = 2
    _player()
    first = login("ada@example.com", PASSWORD)
    second = login("ada@example.com", PASSWORD)
    third = login("ada@example.com", PASSWORD)

    assert load_session(first.token) is None
    assert load_session(second.token) is not None
    assert load_session(third.token) is not None
    assert PlayerSession.objects.count() == 2


@pytest.mark.django_db
def test_password_change_and_deactivation_close_every_session() -> None:
    user = _player()
    opened = login("ada@example.com", PASSWORD)
    user.alias = "otro_alias"
    user.save(update_fields=["alias"])
    assert load_session(opened.token) is not None

    user.set_password("otra-clave-larga")
    user.save(update_fields=["password"])
    assert PlayerSession.objects.count() == 0
    assert load_session(opened.token) is None

    kept = login("ada@example.com", "otra-clave-larga")
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert PlayerSession.objects.count() == 0
    assert load_session(kept.token) is None


@pytest.mark.django_db
def test_a_direct_deactivation_fails_on_the_next_read() -> None:
    user = _player()
    opened = login("ada@example.com", PASSWORD)
    User.objects.filter(pk=user.pk).update(is_active=False)

    assert PlayerSession.objects.count() == 1
    assert load_session(opened.token) is None
    assert PlayerSession.objects.count() == 0


@pytest.mark.django_db
def test_email_guesses_are_limited_per_address(settings) -> None:
    settings.LOGIN_EMAIL_LIMIT = 1
    _player()
    login("ada@example.com", PASSWORD)

    with pytest.raises(LoginThrottled):
        login("Ada@example.com", "clave-equivocada")

    other = _player(email="grace@example.com", alias="grace_user")
    assert login(other.email, PASSWORD).user.pk == other.pk
