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
    PasswordMismatch,
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
    assert "contraseña que elegiste" in mail.body
    assert "ignora este mensaje" in mail.body
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


def _verify(user: User | None = None) -> None:
    account = user or User.objects.get()
    account.email_verified_at = timezone.now()
    account.save(update_fields=["email_verified_at"])


@pytest.mark.django_db
def test_pending_registration_is_replaced_and_the_old_link_dies(mailoutbox) -> None:
    _register()
    old = _token(mailoutbox[0].body)

    _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")

    user = User.objects.get()
    assert user.alias == "otro_alias"
    assert user.check_password("otra-clave-larga")
    assert user.email_verified_at is None
    assert user.is_staff is False
    assert len(mailoutbox) == 2
    assert EmailVerification.objects.count() == 1
    with pytest.raises(InvalidConfirmation):
        confirm_email(old, "otra-clave-larga")
    confirm_email(_token(mailoutbox[1].body), "otra-clave-larga")
    user.refresh_from_db()
    assert user.email_verified_at is not None


@pytest.mark.django_db
def test_confirmed_email_does_not_change_the_account_or_send_again(mailoutbox) -> None:
    _register()
    _verify()

    with pytest.raises(RegistrationError) as taken:
        _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")

    assert taken.value.errors == {"email": ["Este correo ya está registrado."]}
    user = User.objects.get()
    assert user.check_password(PASSWORD)
    assert user.alias == "ada_lovelace"
    assert len(mailoutbox) == 1
    assert EmailVerification.objects.count() == 1


@pytest.mark.django_db
def test_staff_and_inactive_accounts_are_not_replaced(mailoutbox) -> None:
    _register()
    user = User.objects.get()
    user.is_staff = True
    user.save(update_fields=["is_staff"])

    with pytest.raises(RegistrationError) as staff:
        _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")

    assert staff.value.errors == {"email": ["Este correo ya está registrado."]}
    user.refresh_from_db()
    assert user.is_staff is True
    assert user.check_password(PASSWORD)
    assert user.alias == "ada_lovelace"

    user.is_staff = False
    user.is_active = False
    user.save(update_fields=["is_staff", "is_active"])
    with pytest.raises(RegistrationError) as inactive:
        _register(email="ada@example.com", alias="otro_alias", password="otra-clave-larga")

    assert inactive.value.errors == {"email": ["Este correo ya está registrado."]}
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_an_account_without_a_confirmation_row_is_kept(mailoutbox) -> None:
    User.objects.create_user(
        "hecha@example.com",
        PASSWORD,
        alias="hecha_admin",
        birth_date=BORN,
        sex="woman",
    )

    with pytest.raises(RegistrationError) as taken:
        _register(email="HECHA@example.com", alias="otro_alias", password="otra-clave-larga")

    assert taken.value.errors == {"email": ["Este correo ya está registrado."]}
    user = User.objects.get()
    assert user.alias == "hecha_admin"
    assert user.check_password(PASSWORD)
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_taken_email_and_taken_alias_are_reported(mailoutbox) -> None:
    _register()
    _verify()

    with pytest.raises(RegistrationError) as email_only:
        _register(email="ADA@example.com", alias="otro_alias")
    with pytest.raises(RegistrationError) as alias_only:
        _register(email="otro@example.com", alias="ADA_LOVELACE")
    with pytest.raises(RegistrationError) as both:
        _register(email="ADA@example.com", alias="ada_lovelace")

    assert email_only.value.errors == {"email": ["Este correo ya está registrado."]}
    assert alias_only.value.errors == {"alias": ["Ese alias ya está en uso."]}
    assert both.value.errors == {
        "email": ["Este correo ya está registrado."],
        "alias": ["Ese alias ya está en uso."],
    }
    assert User.objects.count() == 1
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_full_clean_replaces_an_unverified_duplicate(mailoutbox) -> None:
    _register()

    with _miss_prechecks():
        _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")

    user = User.objects.get()
    assert user.alias == "otro_alias"
    assert user.check_password("otra-clave-larga")
    assert user.email_verified_at is None
    assert len(mailoutbox) == 2


@pytest.mark.django_db
def test_full_clean_reports_an_alias_collision_on_alias(mailoutbox) -> None:
    _register()

    with _miss_prechecks(), pytest.raises(RegistrationError) as taken:
        _register(email="otro@example.com", alias="ADA_LOVELACE")

    assert taken.value.errors == {"alias": ["Ese alias ya está en uso."]}
    assert User.objects.count() == 1
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_database_constraint_reports_a_confirmed_email_and_an_alias(mailoutbox) -> None:
    _register()
    _verify()
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
        with pytest.raises(RegistrationError) as email_taken:
            _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")
        with pytest.raises(RegistrationError) as alias_taken:
            _register(email="libre@example.com", alias="ADA_LOVELACE")

    assert email_taken.value.errors == {"email": ["Este correo ya está registrado."]}
    assert alias_taken.value.errors == {"alias": ["Ese alias ya está en uso."]}
    user = User.objects.get()
    assert user.alias == "ada_lovelace"
    assert user.check_password(PASSWORD)
    assert len(mailoutbox) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("constraint_name", "expected"),
    [
        ("accounts_user_email_key", {"email": ["Este correo ya está registrado."]}),
        ("accounts_user_alias_ci", {"alias": ["Ese alias ya está en uso."]}),
        ("accounts_user_alias_shape", "raise"),
        ("accounts_user_email_b2644a56_like", "raise"),
        ("accounts_user_pkey", "raise"),
        ("", "raise"),
    ],
)
def test_integrity_errors_follow_the_constraint_name(
    constraint_name: str,
    expected: dict[str, list[str]] | str,
) -> None:
    def explode(self, *args, **kwargs):
        raise _integrity(constraint_name)

    with patch.object(User, "save", explode):
        if expected == "raise":
            with pytest.raises(IntegrityError):
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
def test_validation_error_on_the_email_is_reported() -> None:
    def explode(self, *args, **kwargs):
        raise ValidationError({"email": ["ya existe"], "alias": ["también"]})

    with patch.object(User, "save", explode), pytest.raises(RegistrationError) as error:
        _register(email="nuevo@example.com", alias="nuevo_alias")

    assert error.value.errors == {
        "email": ["Este correo ya está registrado."],
        "alias": ["Ese alias ya está en uso."],
    }
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
def test_a_pending_replacement_reports_save_errors(mailoutbox) -> None:
    _register()

    def constraint(self, *args, **kwargs):
        raise _integrity("accounts_user_alias_ci")

    with patch.object(User, "save", constraint), pytest.raises(RegistrationError) as alias:
        _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")
    assert alias.value.errors == {"alias": ["Ese alias ya está en uso."]}

    def invalid(self, *args, **kwargs):
        raise ValidationError({"birth_date": ["demasiado"]})

    with patch.object(User, "save", invalid), pytest.raises(RegistrationError) as birth:
        _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")
    assert birth.value.errors == {"birth_date": ["demasiado"]}

    user = User.objects.get()
    assert user.alias == "ada_lovelace"
    assert user.check_password(PASSWORD)
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_unknown_token_does_not_check_a_password() -> None:
    _register()

    with patch.object(User, "check_password", return_value=True) as check:
        with pytest.raises(InvalidConfirmation):
            confirm_email("no-existe", PASSWORD)

    check.assert_not_called()
    with pytest.raises(InvalidConfirmation):
        confirm_email("no-existe", "a" * 200)


@pytest.mark.django_db
def test_a_huge_confirmation_password_is_not_hashed(mailoutbox) -> None:
    _register()
    raw = _token(mailoutbox[0].body)

    with patch.object(User, "check_password", return_value=True) as check:
        with pytest.raises(PasswordMismatch):
            confirm_email(raw, "a" * 129)

    check.assert_not_called()
    assert User.objects.get().email_verified_at is None


@pytest.mark.django_db
def test_smtp_failure_rolls_the_account_back(settings) -> None:
    settings.EMAIL_BACKEND = "tests.accounts.test_registration_service.SmtpDownBackend"

    with pytest.raises(MailDeliveryError):
        _register(email="baja@example.com", alias="sin_correo")

    assert User.objects.count() == 0
    assert EmailVerification.objects.count() == 0


@pytest.mark.django_db
def test_smtp_failure_keeps_the_pending_account(settings, mailoutbox) -> None:
    _register()
    settings.EMAIL_BACKEND = "tests.accounts.test_registration_service.SmtpDownBackend"

    with pytest.raises(MailDeliveryError):
        _register(email="ADA@example.com", alias="otro_alias", password="otra-clave-larga")

    user = User.objects.get()
    assert user.alias == "ada_lovelace"
    assert user.check_password(PASSWORD)
    assert EmailVerification.objects.count() == 1
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_confirmation_rejects_empty_unknown_used_and_expired_tokens() -> None:
    with pytest.raises(InvalidConfirmation):
        confirm_email("", PASSWORD)

    _register()
    raw = "uno-token-conocido"
    row = EmailVerification.objects.get()
    row.token_hash = hashlib.sha256(raw.encode()).hexdigest()
    row.save(update_fields=["token_hash"])

    with pytest.raises(InvalidConfirmation):
        confirm_email("otro-token", PASSWORD)
    assert User.objects.get().email_verified_at is None

    row.expires_at = timezone.now() - timedelta(seconds=1)
    row.save(update_fields=["expires_at"])
    with pytest.raises(InvalidConfirmation):
        confirm_email(raw, PASSWORD)
    assert User.objects.get().email_verified_at is None

    row.expires_at = timezone.now() + TOKEN_TTL
    row.save(update_fields=["expires_at"])
    with pytest.raises(PasswordMismatch):
        confirm_email(raw, "otra-clave-larga")
    row.refresh_from_db()
    assert row.used_at is None
    confirm_email(raw, PASSWORD)
    user = User.objects.get()
    verified_at = user.email_verified_at
    assert verified_at is not None
    row.refresh_from_db()
    assert row.used_at == verified_at

    with pytest.raises(InvalidConfirmation):
        confirm_email(raw, PASSWORD)
    user.refresh_from_db()
    assert user.email_verified_at == verified_at


@pytest.mark.django_db
def test_a_later_token_does_not_move_the_verification_time() -> None:
    _register()
    first = "primer-token"
    row = EmailVerification.objects.get()
    row.token_hash = hashlib.sha256(first.encode()).hexdigest()
    row.save(update_fields=["token_hash"])
    confirm_email(first, PASSWORD)
    verified_at = User.objects.get().email_verified_at

    second = "segundo-token"
    EmailVerification.objects.create(
        user=User.objects.get(),
        token_hash=hashlib.sha256(second.encode()).hexdigest(),
        expires_at=timezone.now() + TOKEN_TTL,
    )
    confirm_email(second, PASSWORD)

    user = User.objects.get()
    assert user.email_verified_at == verified_at
    assert user.email_verifications.filter(used_at__isnull=False).count() == 2
