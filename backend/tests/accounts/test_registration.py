"""Registration and email confirmation over HTTP."""

import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.mail.backends.base import BaseEmailBackend
from django.utils import timezone
from fastapi.testclient import TestClient

from apps.accounts.models import EmailVerification, User
from config.asgi import application

ACCEPTED = {"detail": "Si el correo está libre, te enviaremos un enlace para confirmarlo."}


class BrokenBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise OSError("smtp down")


def _payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "email": "ada@example.com",
        "password": "una-clave-larga",
        "alias": "ada_lovelace",
        "birth_date": "1990-01-01",
        "sex": "woman",
    }
    data.update(overrides)
    return data


def _token(message: str) -> str:
    line = next(line for line in message.splitlines() if line.startswith("http"))
    return parse_qs(urlparse(line).query)["token"][0]


@pytest.fixture
def client():
    with TestClient(application) as http:
        yield http


@pytest.mark.django_db(transaction=True)
def test_register_sends_a_hashed_link_and_hides_the_profile(client, mailoutbox) -> None:
    response = client.post("/api/users", json=_payload(email=" Ada@Example.com "))

    assert response.status_code == 202
    assert response.json() == ACCEPTED
    body = response.text
    assert "1990-01-01" not in body
    assert "woman" not in body
    assert "una-clave-larga" not in body

    user = User.objects.get()
    assert user.email == "ada@example.com"
    assert user.email_verified_at is None
    assert len(mailoutbox) == 1
    token = _token(mailoutbox[0].body)
    assert token not in body
    stored = EmailVerification.objects.get()
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert stored.token_hash != token


@pytest.mark.django_db(transaction=True)
def test_existing_email_gets_the_same_response(client, mailoutbox) -> None:
    assert client.post("/api/users", json=_payload()).status_code == 202
    again = client.post(
        "/api/users",
        json=_payload(email="ADA@example.com", alias="otra_persona"),
    )

    assert again.status_code == 202
    assert again.json() == ACCEPTED
    assert User.objects.count() == 1
    assert len(mailoutbox) == 1
    assert User.objects.get().alias == "ada_lovelace"


@pytest.mark.django_db(transaction=True)
def test_register_rejects_alias_age_and_password(client, mailoutbox) -> None:
    taken = client.post("/api/users", json=_payload())
    assert taken.status_code == 202

    alias = client.post("/api/users", json=_payload(email="otro@example.com", alias="ADA_lovelace"))
    assert alias.status_code == 422
    assert alias.json()["errors"]["alias"] == ["Ese alias ya está en uso."]

    young = client.post(
        "/api/users",
        json=_payload(email="joven@example.com", alias="demasiado_joven", birth_date="2016-01-01"),
    )
    assert young.status_code == 422
    assert "birth_date" in young.json()["errors"]

    short = client.post("/api/users", json=_payload(email="corta@example.com", password="corta"))
    assert short.status_code == 422
    assert "password" in short.json()["errors"]

    sex = client.post(
        "/api/users",
        json=_payload(email="sexo@example.com", alias="sexo_malo", sex="nope"),
    )
    assert sex.status_code == 422
    assert "sex" in sex.json()["errors"]
    assert len(mailoutbox) == 1


@pytest.mark.django_db(transaction=True)
def test_confirmation_link_is_single_use(client, mailoutbox) -> None:
    assert client.post("/api/users", json=_payload()).status_code == 202
    token = _token(mailoutbox[0].body)
    user = User.objects.get()

    preview = client.get("/api/users/verify-email", params={"token": token})
    assert preview.status_code == 200
    assert "Confirmar correo" in preview.text
    user.refresh_from_db()
    assert user.email_verified_at is None

    confirmed = client.post("/api/users/verify-email", json={"token": token})
    assert confirmed.status_code == 200
    assert confirmed.json()["detail"] == "Correo confirmado."
    user.refresh_from_db()
    assert user.email_verified_at is not None

    again = client.post("/api/users/verify-email", json={"token": token})
    assert again.status_code == 400
    assert again.json()["errors"]["token"] == ["El enlace no es válido o ha caducado."]


@pytest.mark.django_db(transaction=True)
def test_expired_link_does_not_confirm(client, mailoutbox) -> None:
    assert client.post("/api/users", json=_payload()).status_code == 202
    token = _token(mailoutbox[0].body)
    row = EmailVerification.objects.get()
    row.expires_at = timezone.now() - timedelta(minutes=1)
    row.save(update_fields=["expires_at"])

    response = client.post("/api/users/verify-email", data={"token": token})

    assert response.status_code == 400
    assert "caducado" in response.text
    assert User.objects.get().email_verified_at is None


@pytest.mark.django_db(transaction=True)
def test_mail_failure_does_not_keep_the_user(client, settings) -> None:
    settings.EMAIL_BACKEND = "tests.accounts.test_registration.BrokenBackend"

    response = client.post(
        "/api/users",
        json=_payload(email="baja@example.com", alias="sin_correo"),
    )

    assert response.status_code == 503
    assert User.objects.filter(email="baja@example.com").count() == 0
