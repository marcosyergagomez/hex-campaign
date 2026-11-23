"""Registration and confirmation without the HTTP layer."""

import hashlib
from contextlib import contextmanager
from datetime import date, timedelta
from smtplib import SMTPException
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.exceptions import ValidationError
from django.core.mail.backends.base import BaseEmailBackend
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import EmailVerification, User
from apps.accounts.registration import (
    TOKEN_TTL,
    InvalidConfirmation,
    MailDeliveryError,
    RegistrationError,
    confirm_email,
    register_account,
)

BORN = date(1990, 1, 1)
PASSWORD = "una-clave-larga"


class SmtpDownBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise SMTPException("smtp down")


def _register(**overrides: object) -> None:
    birth_date = overrides.get("birth_date", BORN)
    if not isinstance(birth_date, date):
        raise AssertionError(birth_date)
    register_account(
        email=str(overrides.get("email", "ada@example.com")),
        password=str(overrides.get("password", PASSWORD)),
        alias=str(overrides.get("alias", "ada_lovelace")),
        birth_date=birth_date,
        sex=str(overrides.get("sex", "woman")),
    )


def _token(message: str) -> str:
    line = next(line for line in message.splitlines() if line.startswith("http"))
    return parse_qs(urlparse(line).query)["token"][0]


class _Cause(Exception):
    def __init__(self, constraint_name: str) -> None:
        super().__init__(constraint_name)
        self.diag = SimpleNamespace(constraint_name=constraint_name)


def _integrity(constraint_name: str) -> IntegrityError:
    error = IntegrityError("constraint")
    error.__cause__ = _Cause(constraint_name)
    return error


def _skip_clean(self) -> None:
    return None


@contextmanager
def _miss_prechecks():
    real_filter = User.objects.filter
    state = {"left": 2}

    def hide_prechecks(*args, **kwargs):
        queryset = real_filter(*args, **kwargs)
        original = queryset.exists

        def exists() -> bool:
            if state["left"] > 0:
                state["left"] -= 1
                return False
            return original()

        queryset.exists = exists
        return queryset

    with patch("apps.accounts.registration.User.objects.filter", side_effect=hide_prechecks):
        yield


@pytest.mark.django_db
def test_register_stores_the_profile_and_mails_only_the_link(mailoutbox, settings) -> None:
    before = timezone.now()
    with patch("apps.accounts.registration.secrets.token_urlsafe", return_value="uno+dos/tres"):
        _register(email="  Ada@Example.com ", alias="  Ada_Lovelace ")
    after = timezone.now()

    user = User.objects.get()
    assert user.email == "ada@example.com"
    assert user.alias == "Ada_Lovelace"
    assert user.birth_date == BORN
    assert user.sex == "woman"
    assert user.is_active is True
    assert user.email_verified_at is None
    assert user.password.startswith("argon2")
    assert user.check_password(PASSWORD)
    assert PASSWORD not in user.password

    mail = mailoutbox[0]
    assert mail.subject == "Confirma tu correo"
    assert mail.from_email == settings.DEFAULT_FROM_EMAIL
    assert mail.to == ["ada@example.com"]
    assert "24 horas" in mail.body
    assert "una vez" in mail.body
    assert BORN.isoformat() not in mail.body
    assert "woman" not in mail.body
    assert PASSWORD not in mail.body
    token = _token(mail.body)
    assert token == "uno+dos/tres"
    link = f"{settings.API_ORIGIN}/api/users/verify-email?token="
    assert link in mail.body

    row = EmailVerification.objects.get()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert row.token_hash != token
    assert row.used_at is None
    assert before + TOKEN_TTL <= row.expires_at <= after + TOKEN_TTL
    assert str(row) == f"{user.pk} {row.expires_at:%Y-%m-%d}"


@pytest.mark.django_db
def test_shape_is_checked_before_the_address_is_looked_up(mailoutbox) -> None:
    _register()

    with pytest.raises(RegistrationError) as too_young:
        _register(email="ADA@example.com", alias="otra_persona", birth_date=date(2020, 1, 1))

    assert "birth_date" in too_young.value.errors
    assert User.objects.count() == 1
    assert len(mailoutbox) == 1
    assert User.objects.get().alias == "ada_lovelace"


@pytest.mark.django_db
def test_known_email_does_not_change_the_account_or_send_again(mailoutbox) -> None:
    _register()

    _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")

    user = User.objects.get()
    assert user.check_password(PASSWORD)
    assert user.alias == "ada_lovelace"
    assert len(mailoutbox) == 1
    assert EmailVerification.objects.count() == 1


@pytest.mark.django_db
def test_alias_collision_is_reported_only_when_the_email_is_free(mailoutbox) -> None:
    _register()

    _register(email="ADA@example.com", alias="otro_alias")
    with pytest.raises(RegistrationError) as taken:
        _register(email="otro@example.com", alias="ADA_LOVELACE")

    assert taken.value.errors == {"alias": ["Ese alias ya está en uso."]}
    assert User.objects.count() == 1
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_full_clean_hides_a_duplicate_email(mailoutbox) -> None:
    _register()

    with _miss_prechecks():
        _register(email="ADA@example.com", alias="otro_alias")

    assert User.objects.count() == 1
    assert User.objects.get().alias == "ada_lovelace"
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_full_clean_reports_an_alias_collision_on_alias(mailoutbox) -> None:
    _register()

    with _miss_prechecks(), pytest.raises(RegistrationError) as taken:
        _register(email="otro@example.com", alias="ADA_LOVELACE")

    assert taken.value.errors == {"alias": ["Ese alias ya está en uso."]}
    assert User.objects.count() == 1
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_database_constraint_hides_email_and_reports_alias(mailoutbox) -> None:
    _register()
    real_filter = User.objects.filter

    def hide_existing(*args, **kwargs):
        queryset = real_filter(*args, **kwargs)

        def missing() -> bool:
            return False

        queryset.exists = missing
        return queryset

    with (
        patch.object(User, "full_clean", _skip_clean),
        patch("apps.accounts.registration.User.objects.filter", side_effect=hide_existing),
    ):
        _register(email="ADA@example.com", alias="otro_alias")
        with pytest.raises(RegistrationError) as taken:
            _register(email="libre@example.com", alias="ADA_LOVELACE")

    assert taken.value.errors == {"alias": ["Ese alias ya está en uso."]}
    assert User.objects.count() == 1
    assert len(mailoutbox) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("constraint_name", "expected"),
    [
        ("accounts_user_email_key", None),
        ("accounts_user_alias_ci", {"alias": ["Ese alias ya está en uso."]}),
        ("accounts_user_pkey", "raise"),
        ("", "raise"),
    ],
)
def test_integrity_errors_follow_the_constraint_name(
    constraint_name: str,
    expected: dict[str, list[str]] | None | str,
) -> None:
    def explode(self, *args, **kwargs):
        raise _integrity(constraint_name)

    with patch.object(User, "save", explode):
        if expected == "raise":
            with pytest.raises(IntegrityError):
                _register(email="nuevo@example.com", alias="nuevo_alias")
        elif expected is None:
            _register(email="nuevo@example.com", alias="nuevo_alias")
        else:
            with pytest.raises(RegistrationError) as error:
                _register(email="nuevo@example.com", alias="nuevo_alias")
            assert error.value.errors == expected
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_validation_error_without_a_field_uses_a_generic_message() -> None:
    def explode(self, *args, **kwargs):
        raise ValidationError("boom")

    with (
        patch.object(User, "save", explode),
        pytest.raises(RegistrationError) as error,
    ):
        _register(email="nuevo@example.com", alias="nuevo_alias")

    assert error.value.errors == {"email": ["No se ha podido crear la cuenta."]}


@pytest.mark.django_db
def test_validation_error_on_the_email_stays_silent() -> None:
    def explode(self, *args, **kwargs):
        raise ValidationError({"email": ["ya existe"], "alias": ["también"]})

    with patch.object(User, "save", explode):
        _register(email="nuevo@example.com", alias="nuevo_alias")

    assert User.objects.count() == 0


@pytest.mark.django_db
def test_validation_error_on_another_field_is_returned() -> None:
    def explode(self, *args, **kwargs):
        raise ValidationError({"birth_date": ["demasiado"]})

    with (
        patch.object(User, "save", explode),
        pytest.raises(RegistrationError) as error,
    ):
        _register(email="nuevo@example.com", alias="nuevo_alias")

    assert error.value.errors == {"birth_date": ["demasiado"]}


@pytest.mark.django_db
def test_smtp_failure_rolls_the_account_back(settings) -> None:
    settings.EMAIL_BACKEND = "tests.accounts.test_registration_service.SmtpDownBackend"

    with pytest.raises(MailDeliveryError):
        _register(email="baja@example.com", alias="sin_correo")

    assert User.objects.count() == 0
    assert EmailVerification.objects.count() == 0


@pytest.mark.django_db
def test_confirmation_rejects_empty_unknown_used_and_expired_tokens() -> None:
    with pytest.raises(InvalidConfirmation):
        confirm_email("")

    _register()
    raw = "uno-token-conocido"
    row = EmailVerification.objects.get()
    row.token_hash = hashlib.sha256(raw.encode()).hexdigest()
    row.save(update_fields=["token_hash"])

    with pytest.raises(InvalidConfirmation):
        confirm_email("otro-token")
    assert User.objects.get().email_verified_at is None

    row.expires_at = timezone.now() - timedelta(seconds=1)
    row.save(update_fields=["expires_at"])
    with pytest.raises(InvalidConfirmation):
        confirm_email(raw)
    assert User.objects.get().email_verified_at is None

    row.expires_at = timezone.now() + TOKEN_TTL
    row.save(update_fields=["expires_at"])
    confirm_email(raw)
    user = User.objects.get()
    verified_at = user.email_verified_at
    assert verified_at is not None
    row.refresh_from_db()
    assert row.used_at == verified_at

    with pytest.raises(InvalidConfirmation):
        confirm_email(raw)
    user.refresh_from_db()
    assert user.email_verified_at == verified_at


@pytest.mark.django_db
def test_a_later_token_does_not_move_the_verification_time() -> None:
    _register()
    first = "primer-token"
    row = EmailVerification.objects.get()
    row.token_hash = hashlib.sha256(first.encode()).hexdigest()
    row.save(update_fields=["token_hash"])
    confirm_email(first)
    verified_at = User.objects.get().email_verified_at

    second = "segundo-token"
    EmailVerification.objects.create(
        user=User.objects.get(),
        token_hash=hashlib.sha256(second.encode()).hexdigest(),
        expires_at=timezone.now() + TOKEN_TTL,
    )
    confirm_email(second)

    user = User.objects.get()
    assert user.email_verified_at == verified_at
    assert user.email_verifications.filter(used_at__isnull=False).count() == 2
