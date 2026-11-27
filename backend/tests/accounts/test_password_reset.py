"""A reset link works once, and an unknown email looks the same as a known one."""

import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from apps.accounts.models import PasswordReset, User
from config.asgi import application
from tests.accounts.test_registration import _payload


@pytest.fixture
def client():
    with TestClient(application) as http:
        http.headers.update({"origin": "http://testserver"})
        yield http


def _token(message: str) -> str:
    for line in message.splitlines():
        if line.startswith("http"):
            return parse_qs(urlparse(line).query)["token"][0]
    raise AssertionError(message)


@pytest.mark.django_db(transaction=True)
def test_unknown_email_gets_the_same_answer_and_no_mail(client, mailoutbox) -> None:
    response = client.post("/api/password-reset", json={"email": "nadie@example.com"})

    assert response.status_code == 202
    assert response.json()["detail"] == "Si el correo está registrado, te enviaremos un enlace."
    assert mailoutbox == []
    assert PasswordReset.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_confirmed_account_can_set_a_new_password(client, mailoutbox) -> None:
    assert client.post("/api/users", json=_payload()).status_code == 202
    from tests.accounts.test_registration import _token as confirm_token

    confirmed = client.post(
        "/api/users/verify-email",
        json={"token": confirm_token(mailoutbox[0].body), "password": "una-clave-larga"},
    )
    assert confirmed.status_code == 200
    mailoutbox.clear()

    asked = client.post("/api/password-reset", json={"email": "Ada@Example.com"})
    assert asked.status_code == 202
    assert len(mailoutbox) == 1
    raw = _token(mailoutbox[0].body)
    stored = PasswordReset.objects.get()
    assert stored.token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert stored.used_at is None

    saved = client.post(
        "/api/password-reset/confirm",
        json={"token": raw, "password": "otra-clave-larga"},
    )
    assert saved.status_code == 200, saved.text
    user = User.objects.get()
    assert user.check_password("otra-clave-larga")
    stored.refresh_from_db()
    assert stored.used_at is not None

    again = client.post(
        "/api/password-reset/confirm",
        json={"token": raw, "password": "tercera-clave-larga"},
    )
    assert again.status_code == 400
    user.refresh_from_db()
    assert user.check_password("otra-clave-larga")
