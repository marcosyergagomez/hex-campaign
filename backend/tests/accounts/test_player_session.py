"""The browser session is an HttpOnly cookie plus a CSRF token."""

import re
from datetime import date

import pytest
from django.utils import timezone
from fastapi.testclient import TestClient

from api.player_session import CSRF_COOKIE, CSRF_MESSAGE, ORIGIN_MESSAGE, SESSION_COOKIE
from apps.accounts.models import PlayerSession, User
from apps.accounts.throttle import clear_login_limits
from config.asgi import application

PASSWORD = "una-clave-larga"
CREDENTIALS = {"errors": {"credentials": ["El correo o la contraseña no son correctos."]}}


@pytest.fixture(autouse=True)
def _reset_login_limits():
    clear_login_limits()
    yield
    clear_login_limits()


@pytest.fixture
def client():
    with TestClient(application, base_url="https://testserver") as http:
        yield http


def _player(
    email: str = "ada@example.com",
    password: str = PASSWORD,
    *,
    alias: str = "ada_lovelace",
    verified: bool = True,
    active: bool = True,
) -> User:
    user = User.objects.create_user(
        email,
        password,
        alias=alias,
        birth_date=date(1990, 1, 1),
        sex="woman",
        is_active=active,
    )
    if verified:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


def _login(
    client,
    *,
    email="ada@example.com",
    password=PASSWORD,
    origin="http://testserver",
    referer=None,
):
    headers = {}
    if origin is not None:
        headers["origin"] = origin
    if referer is not None:
        headers["referer"] = referer
    return client.post("/api/session", json={"email": email, "password": password}, headers=headers)


def _logout(
    client,
    *,
    csrf: str | None = None,
    send_csrf: bool = True,
    origin="http://testserver",
):
    headers = {}
    if origin is not None:
        headers["origin"] = origin
    if send_csrf:
        token = client.cookies.get(CSRF_COOKIE) if csrf is None else csrf
        if token:
            headers["x-csrf-token"] = token
    return client.post("/api/session/logout", headers=headers)


def _cookie_headers(response) -> dict[str, str]:
    found = {}
    for header in response.headers.get_list("set-cookie"):
        found[header.split("=", 1)[0]] = header
    return found


def _attrs(header: str) -> set[str]:
    return {part.strip().lower() for part in header.split(";")[1:]}


@pytest.mark.django_db(transaction=True)
def test_login_sets_host_cookies_and_hides_the_profile(client) -> None:
    _player()

    response = _login(client, email=" Ada@Example.com ")

    assert response.status_code == 200
    assert response.json() == {"email": "ada@example.com", "alias": "ada_lovelace"}
    assert "1990" not in response.text
    assert "woman" not in response.text
    assert PASSWORD not in response.text
    cookies = _cookie_headers(response)
    session_attrs = _attrs(cookies[SESSION_COOKIE])
    csrf_attrs = _attrs(cookies[CSRF_COOKIE])
    assert "httponly" in session_attrs
    assert "httponly" not in csrf_attrs
    for attrs in (session_attrs, csrf_attrs):
        assert "secure" in attrs
        assert "samesite=lax" in attrs
        assert "path=/" in attrs
        assert not any(attr.startswith("domain=") for attr in attrs)
    age = int(re.search(r"max-age=(\d+)", cookies[SESSION_COOKIE], re.I).group(1))
    assert 15552000 - 120 <= age <= 15552000
    assert "sessionid" not in cookies
    who = client.get("/api/session")
    assert who.status_code == 200
    assert who.json() == {"email": "ada@example.com", "alias": "ada_lovelace"}


@pytest.mark.django_db(transaction=True)
def test_failed_logins_share_one_answer(client) -> None:
    _player()
    _player(email="quiet@example.com", alias="quiet_user", verified=False)
    _player(email="off@example.com", alias="off_user", active=False)

    unknown = _login(client, email="nadie@example.com")
    wrong = _login(client, password="clave-equivocada")
    quiet = _login(client, email="quiet@example.com")
    inactive = _login(client, email="off@example.com")

    assert unknown.status_code == wrong.status_code == quiet.status_code == inactive.status_code
    assert unknown.json() == wrong.json() == quiet.json() == inactive.json() == CREDENTIALS
    assert PlayerSession.objects.count() == 0
    assert client.get("/api/session").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_login_requires_this_origin(client) -> None:
    _player()

    missing = _login(client, origin=None)
    foreign = _login(client, origin="https://evil.test")
    prefixed = _login(client, origin=None, referer="http://testserver.evil/mapa")
    referred = _login(client, origin=None, referer="http://testserver/mapa")

    assert missing.status_code == foreign.status_code == prefixed.status_code == 403
    assert missing.json()["errors"]["origin"] == [ORIGIN_MESSAGE]
    assert referred.status_code == 200
    assert PlayerSession.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_logout_needs_the_csrf_token_and_leaves_other_sessions(client) -> None:
    _player()
    _login(client)
    with TestClient(application, base_url="https://testserver") as other:
        _login(other)
        assert PlayerSession.objects.count() == 2

        blocked = _logout(client, send_csrf=False)
        mismatched = _logout(client, csrf="otro-token-distinto")
        assert blocked.status_code == mismatched.status_code == 403
        assert blocked.json()["errors"]["csrf"] == [CSRF_MESSAGE]
        assert client.get("/api/session").status_code == 200

        closed = _logout(client)
        assert closed.status_code == 204
        cleared = " ".join(_cookie_headers(closed).values()).lower()
        assert "max-age=0" in cleared
        assert client.get("/api/session").status_code == 401
        assert other.get("/api/session").status_code == 200
        assert PlayerSession.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_logout_without_a_session_clears_the_cookies(client) -> None:
    response = _logout(client)

    assert response.status_code == 204
    assert SESSION_COOKIE in _cookie_headers(response)


@pytest.mark.django_db(transaction=True)
def test_login_from_one_address_is_rate_limited(client, settings) -> None:
    settings.LOGIN_IP_LIMIT = 1
    _player()
    _player(email="grace@example.com", alias="grace_user")

    assert _login(client).status_code == 200
    blocked = _login(client, email="grace@example.com")

    assert blocked.status_code == 429
    assert blocked.json()["errors"]["credentials"] == [
        "Demasiados intentos. Prueba de nuevo en unos minutos."
    ]


@pytest.mark.django_db(transaction=True)
def test_a_huge_login_body_is_rejected(client) -> None:
    response = client.post(
        "/api/session/",
        content=b'{"password":"' + b"a" * 5000 + b'"}',
        headers={"content-type": "application/json", "origin": "http://testserver"},
    )

    assert response.status_code == 413
    assert response.json()["errors"]["credentials"] == ["La solicitud es demasiado grande."]
