"""Registration and email confirmation over HTTP."""

import hashlib
from datetime import date, timedelta
from smtplib import SMTPException
from typing import get_args
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


class SmtpDownBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise SMTPException("smtp down")


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


def _years_ago(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


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
    assert user.alias == "ada_lovelace"
    assert user.birth_date.isoformat() == "1990-01-01"
    assert user.sex == "woman"
    assert user.is_active is True
    assert user.email_verified_at is None
    assert user.password.startswith("argon2")
    assert user.check_password("una-clave-larga")
    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "Confirma tu correo"
    assert mailoutbox[0].to == ["ada@example.com"]
    assert "24 horas" in mailoutbox[0].body
    assert "http://testserver/api/users/verify-email?token=" in mailoutbox[0].body
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

    one_day_under = (_years_ago(timezone.localdate(), 16) + timedelta(days=1)).isoformat()
    young = client.post(
        "/api/users",
        json=_payload(
            email="joven@example.com",
            alias="demasiado_joven",
            birth_date=one_day_under,
        ),
    )
    assert young.status_code == 422
    assert young.json()["errors"]["birth_date"] == ["Hay que tener al menos 16 años."]

    short = client.post("/api/users", json=_payload(email="corta@example.com", password="corta"))
    assert short.status_code == 422
    assert "12" in short.json()["errors"]["password"][0]

    sex = client.post(
        "/api/users",
        json=_payload(email="sexo@example.com", alias="sexo_malo", sex="nope"),
    )
    assert sex.status_code == 422
    assert sex.json()["errors"]["sex"] == ["Elige woman, man, other o undisclosed."]
    assert len(mailoutbox) == 1


@pytest.mark.django_db(transaction=True)
def test_confirmation_link_is_single_use(client, mailoutbox) -> None:
    assert client.post("/api/users", json=_payload()).status_code == 202
    token = _token(mailoutbox[0].body)
    user = User.objects.get()

    preview = client.get("/api/users/verify-email", params={"token": token})
    assert preview.status_code == 200
    assert "Confirmar correo" in preview.text
    assert 'content="noindex"' in preview.text
    assert f'value="{token}"' in preview.text
    user.refresh_from_db()
    assert user.email_verified_at is None
    assert EmailVerification.objects.get().used_at is None

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
@pytest.mark.parametrize(
    "backend",
    [
        "tests.accounts.test_registration.BrokenBackend",
        "tests.accounts.test_registration.SmtpDownBackend",
    ],
)
def test_mail_failure_does_not_keep_the_user(client, settings, backend: str) -> None:
    settings.EMAIL_BACKEND = backend

    response = client.post(
        "/api/users",
        json=_payload(email="baja@example.com", alias="sin_correo"),
    )

    assert response.status_code == 503
    assert response.json() == {"errors": {"email": ["No se ha podido enviar el correo."]}}
    assert User.objects.filter(email="baja@example.com").count() == 0
    assert EmailVerification.objects.count() == 0


def test_api_sex_codes_match_the_model() -> None:
    from api.app import RegisterPayload
    from apps.accounts.validation import Sex

    assert set(get_args(RegisterPayload.model_fields["sex"].annotation)) == set(Sex.values)


def test_missing_token_is_rejected(client) -> None:
    response = client.get("/api/users/verify-email")

    assert response.status_code == 400
    assert "caducado" in response.text
    assert 'content="noindex"' in response.text


@pytest.mark.django_db(transaction=True)
def test_register_rejects_a_malformed_body(client) -> None:
    missing = client.post("/api/users", json={})

    assert missing.status_code == 422
    errors = missing.json()["errors"]
    for field in ("email", "password", "alias", "birth_date"):
        assert errors[field] == ["Este campo es obligatorio."]
    assert errors["sex"] == ["Elige woman, man, other o undisclosed."]

    invalid = client.post("/api/users", json=_payload(birth_date="no-es-fecha"))
    assert invalid.status_code == 422
    assert invalid.json()["errors"]["birth_date"] == ["Dato no válido."]

    blank = client.post("/api/users", json=_payload(email=" ", password=" ", alias=" "))
    assert blank.status_code == 422
    blank_errors = blank.json()["errors"]
    assert blank_errors["email"] == ["Introduce un correo válido."]
    assert blank_errors["alias"] == ["El alias usa de 3 a 24 letras, números o guion bajo."]
    assert "12" in blank_errors["password"][0]
    assert User.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_register_accepts_bounds_and_every_sex(client) -> None:
    today = timezone.localdate()
    exact = client.post(
        "/api/users",
        json=_payload(
            email="mayor@example.com",
            alias="abc",
            birth_date=_years_ago(today, 16).isoformat(),
            password="123456789012",
        ),
    )
    assert exact.status_code == 202

    long_alias = client.post(
        "/api/users",
        json=_payload(email="largo@example.com", alias="a" * 24),
    )
    assert long_alias.status_code == 202

    for sex in ("woman", "man", "other", "undisclosed"):
        created = client.post(
            "/api/users",
            json=_payload(email=f"{sex}@example.com", alias=f"sexo_{sex}", sex=sex),
        )
        assert created.status_code == 202
        assert User.objects.get(email=f"{sex}@example.com").sex == sex

    future = client.post(
        "/api/users",
        json=_payload(
            email="futuro@example.com",
            alias="aun_no_nace",
            birth_date=(today + timedelta(days=1)).isoformat(),
        ),
    )
    assert future.status_code == 422
    assert "16" in future.json()["errors"]["birth_date"][0]

    short_password = client.post(
        "/api/users",
        json=_payload(email="once@example.com", alias="once_caracter", password="12345678901"),
    )
    assert short_password.status_code == 422

    hyphen = client.post(
        "/api/users",
        json=_payload(email="guion@example.com", alias="a-b"),
    )
    assert hyphen.status_code == 422
    assert hyphen.json()["errors"]["alias"] == [
        "El alias usa de 3 a 24 letras, números o guion bajo."
    ]
    assert User.objects.filter(email="guion@example.com").count() == 0


@pytest.mark.django_db(transaction=True)
def test_invalid_profile_on_a_known_email_stays_a_validation_error(client, mailoutbox) -> None:
    assert client.post("/api/users", json=_payload()).status_code == 202

    again = client.post(
        "/api/users",
        json=_payload(email="ADA@example.com", alias="otro_alias", birth_date="2020-01-01"),
    )

    assert again.status_code == 422
    assert "birth_date" in again.json()["errors"]
    assert User.objects.count() == 1
    assert len(mailoutbox) == 1
    assert User.objects.get().alias == "ada_lovelace"


@pytest.mark.django_db(transaction=True)
def test_form_post_confirms_and_bad_tokens_do_not(client, mailoutbox) -> None:
    assert client.post("/api/users", json=_payload()).status_code == 202
    token = _token(mailoutbox[0].body)

    unknown = client.post("/api/users/verify-email", json={"token": "no-existe"})
    assert unknown.status_code == 400
    assert unknown.json()["errors"]["token"] == ["El enlace no es válido o ha caducado."]

    garbage = client.post(
        "/api/users/verify-email",
        content=b"{",
        headers={"content-type": "application/json"},
    )
    assert garbage.status_code == 400
    assert garbage.json()["errors"]["token"] == ["El enlace no es válido o ha caducado."]

    number = client.post("/api/users/verify-email", json={"token": 15})
    assert number.status_code == 400

    blank = client.post("/api/users/verify-email", data={"token": ""})
    assert blank.status_code == 400
    assert "caducado" in blank.text
    assert User.objects.get().email_verified_at is None

    confirmed = client.post("/api/users/verify-email", data={"token": token})
    assert confirmed.status_code == 200
    assert "Correo confirmado." in confirmed.text
    assert "text/html" in confirmed.headers["content-type"]
    assert User.objects.get().email_verified_at is not None

    repeated = client.post("/api/users/verify-email", data={"token": token})
    assert repeated.status_code == 400
    assert "caducado" in repeated.text
