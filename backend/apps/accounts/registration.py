"""Open registration and the one-time confirmation link.

A confirmed email is reported to the person registering.
An unconfirmed signup can be replaced, because the mailbox has not proved it yet.
The link does not confirm the account unless the password matches.
The mailbox is the only place that receives the raw token.
"""

import hashlib
import secrets
import threading
from datetime import date, timedelta
from smtplib import SMTPException
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models.functions import Lower
from django.utils import timezone

from .models import EmailVerification, User
from .validation import (
    EMAIL_TAKEN,
    MAX_PASSWORD_LENGTH,
    canonical_alias,
    canonical_email,
    registration_errors,
)

ACCEPTED_DETAIL = "Te enviaremos un enlace para confirmar el correo."
ALIAS_TAKEN = "Ese alias ya está en uso."
PASSWORD_MISMATCH = "La contraseña no coincide."
TOKEN_TTL = timedelta(hours=24)
_EMAIL_CONSTRAINT = "accounts_user_email_key"
_ALIAS_CONSTRAINT = "accounts_user_alias_ci"
# Argon2 holds a large memory block, so only two hashes run at once.
_HASH_SLOTS = threading.Semaphore(2)


class RegistrationError(Exception):
    def __init__(self, errors: dict[str, list[str]]):
        self.errors = errors
        super().__init__(errors)


class MailDeliveryError(Exception):
    pass


class InvalidConfirmation(Exception):
    pass


class PasswordMismatch(Exception):
    pass


class _NoPendingAccount(Exception):
    pass


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _set_password(user: User, password: str) -> None:
    with _HASH_SLOTS:
        user.set_password(password)


def _alias_taken(alias: str, *, except_user_id: int | None = None) -> bool:
    folded = alias.lower()
    queryset = User.objects.alias(alias_key=Lower("alias")).filter(alias_key=folded)
    if except_user_id is not None:
        queryset = queryset.exclude(pk=except_user_id)
    return queryset.exists()


def _is_replaceable(user: User) -> bool:
    blocked = user.email_verified_at is not None or user.is_staff or user.is_superuser
    if blocked or not user.is_active:
        return False
    if user.groups.exists() or user.user_permissions.exists():
        return False
    return user.email_verifications.exists()


def _raise_for_integrity(exc: IntegrityError) -> None:
    name = _constraint_name(exc)
    if name == _ALIAS_CONSTRAINT:
        raise RegistrationError({"alias": [ALIAS_TAKEN]}) from exc
    if name == _EMAIL_CONSTRAINT:
        raise RegistrationError({"email": [EMAIL_TAKEN]}) from exc
    raise


def _constraint_name(exc: IntegrityError) -> str:
    cause = exc.__cause__
    diag = getattr(cause, "diag", None)
    return getattr(diag, "constraint_name", "") or ""


def _error_codes(exc: ValidationError) -> set[str]:
    if hasattr(exc, "error_dict"):
        groups = exc.error_dict.values()
    else:
        groups = [exc.error_list]
    return {item.code for group in groups for item in group if item.code}


def register_account(
    *,
    email: str,
    password: str,
    alias: str,
    birth_date: date,
    sex: str,
) -> None:
    errors = registration_errors(
        email=email,
        password=password,
        alias=alias,
        birth_date=birth_date,
        sex=sex,
        today=timezone.localdate(),
    )
    if errors:
        raise RegistrationError(errors)

    normalized_email = canonical_email(email)
    cleaned_alias = canonical_alias(alias)
    existing = User.objects.filter(email=normalized_email).first()
    if existing is None:
        if _alias_taken(cleaned_alias):
            raise RegistrationError({"alias": [ALIAS_TAKEN]})
        _store_new_account(
            email=normalized_email,
            password=password,
            alias=cleaned_alias,
            birth_date=birth_date,
            sex=sex,
        )
        return

    if _is_replaceable(existing):
        if _alias_taken(cleaned_alias, except_user_id=existing.pk):
            raise RegistrationError({"alias": [ALIAS_TAKEN]})
        try:
            _take_pending_account(
                email=normalized_email,
                password=password,
                alias=cleaned_alias,
                birth_date=birth_date,
                sex=sex,
            )
        except _NoPendingAccount:
            if _alias_taken(cleaned_alias):
                raise RegistrationError({"alias": [ALIAS_TAKEN]})
            _store_new_account(
                email=normalized_email,
                password=password,
                alias=cleaned_alias,
                birth_date=birth_date,
                sex=sex,
            )
        return

    taken = {"email": [EMAIL_TAKEN]}
    if _alias_taken(cleaned_alias):
        taken["alias"] = [ALIAS_TAKEN]
    raise RegistrationError(taken)


def _store_new_account(
    *,
    email: str,
    password: str,
    alias: str,
    birth_date: date,
    sex: str,
) -> None:
    try:
        with transaction.atomic():
            user = User(email=email, alias=alias, birth_date=birth_date, sex=sex)
            _set_password(user, password)
            user.save()
            _issue_confirmation(user)
    except ValidationError as exc:
        if "email" not in set(getattr(exc, "message_dict", {})):
            _reraise(exc)
        try:
            _take_pending_account(
                email=email,
                password=password,
                alias=alias,
                birth_date=birth_date,
                sex=sex,
            )
        except _NoPendingAccount:
            _reraise(exc)
    except IntegrityError as exc:
        name = _constraint_name(exc)
        if name == _EMAIL_CONSTRAINT:
            try:
                _take_pending_account(
                    email=email,
                    password=password,
                    alias=alias,
                    birth_date=birth_date,
                    sex=sex,
                )
            except _NoPendingAccount:
                raise RegistrationError({"email": [EMAIL_TAKEN]}) from exc
            return
        _raise_for_integrity(exc)


def _take_pending_account(
    *,
    email: str,
    password: str,
    alias: str,
    birth_date: date,
    sex: str,
) -> None:
    try:
        with transaction.atomic():
            user = User.objects.select_for_update().filter(email=email).first()
            if user is None:
                raise _NoPendingAccount
            if not _is_replaceable(user):
                taken = {"email": [EMAIL_TAKEN]}
                if _alias_taken(alias):
                    taken["alias"] = [ALIAS_TAKEN]
                raise RegistrationError(taken)
            if _alias_taken(alias, except_user_id=user.pk):
                raise RegistrationError({"alias": [ALIAS_TAKEN]})
            user.alias = alias
            user.birth_date = birth_date
            user.sex = sex
            _set_password(user, password)
            user.save()
            user.email_verifications.all().delete()
            _issue_confirmation(user)
    except ValidationError as exc:
        _reraise(exc)
    except IntegrityError as exc:
        _raise_for_integrity(exc)


def _issue_confirmation(user: User) -> None:
    raw_token = secrets.token_urlsafe(32)
    EmailVerification.objects.create(
        user=user,
        token_hash=_digest(raw_token),
        expires_at=timezone.now() + TOKEN_TTL,
    )
    _send_confirmation(user.email, raw_token)


def _token_is_open(row: EmailVerification | None) -> bool:
    return row is not None and row.used_at is None and row.expires_at > timezone.now()


def confirm_email(raw_token: str, password: str) -> None:
    if not raw_token:
        raise InvalidConfirmation
    row = (
        EmailVerification.objects.select_related("user")
        .filter(token_hash=_digest(raw_token))
        .first()
    )
    if not _token_is_open(row) or row is None:
        raise InvalidConfirmation
    if len(password) > MAX_PASSWORD_LENGTH or not row.user.check_password(password):
        raise PasswordMismatch
    known_hash = row.user.password
    with transaction.atomic():
        try:
            user = User.objects.select_for_update().get(pk=row.user_id)
        except User.DoesNotExist:
            raise InvalidConfirmation from None
        locked = EmailVerification.objects.select_for_update().filter(pk=row.pk).first()
        if not _token_is_open(locked) or locked is None:
            raise InvalidConfirmation
        if user.password != known_hash and not user.check_password(password):
            raise PasswordMismatch
        now = timezone.now()
        locked.used_at = now
        locked.save(update_fields=["used_at"])
        if user.email_verified_at is None:
            User.objects.filter(pk=user.pk, email_verified_at__isnull=True).update(
                email_verified_at=now
            )


def _send_confirmation(email: str, raw_token: str) -> None:
    link = f"{settings.API_ORIGIN}/api/users/verify-email?{urlencode({'token': raw_token})}"
    message = (
        "Confirma tu correo en Hex Campaign.\n\n"
        f"{link}\n\n"
        "El enlace caduca a las 24 horas y solo puede usarse una vez.\n"
        "En la página tendrás que escribir la contraseña que elegiste al registrarte.\n"
        "Si no has pedido este alta, ignora este mensaje.\n"
    )
    try:
        send_mail(
            subject="Confirma tu correo",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except (OSError, SMTPException) as exc:
        raise MailDeliveryError from exc


def _reraise(exc: ValidationError) -> None:
    fields = set(getattr(exc, "message_dict", {}))
    codes = _error_codes(exc)
    errors: dict[str, list[str]] = {}
    if "email" in fields:
        errors["email"] = [EMAIL_TAKEN]
    if "alias_taken" in codes or "alias" in fields:
        errors["alias"] = [ALIAS_TAKEN]
    if not errors and fields:
        errors = {key: list(value) for key, value in exc.message_dict.items()}
    if not errors:
        errors = {"email": ["No se ha podido crear la cuenta."]}
    raise RegistrationError(errors) from exc
