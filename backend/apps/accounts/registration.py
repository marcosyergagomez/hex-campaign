"""Open registration and the one-time confirmation link.

The HTTP response does not say whether the email was already registered.
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
from .validation import canonical_alias, canonical_email, registration_errors

ACCEPTED_DETAIL = "Si el correo está libre, te enviaremos un enlace para confirmarlo."
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


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _set_password(user: User, password: str) -> None:
    with _HASH_SLOTS:
        user.set_password(password)


def _alias_taken(alias: str) -> bool:
    folded = alias.lower()
    return User.objects.alias(alias_key=Lower("alias")).filter(alias_key=folded).exists()


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
    if User.objects.filter(email=normalized_email).exists():
        # Same hash cost as a new account, so the timing does not give the address away.
        _set_password(User(), password)
        return
    if _alias_taken(cleaned_alias):
        raise RegistrationError({"alias": ["Ese alias ya está en uso."]})

    try:
        with transaction.atomic():
            user = User(
                email=normalized_email,
                alias=cleaned_alias,
                birth_date=birth_date,
                sex=sex,
            )
            _set_password(user, password)
            user.save()
            raw_token = secrets.token_urlsafe(32)
            EmailVerification.objects.create(
                user=user,
                token_hash=_digest(raw_token),
                expires_at=timezone.now() + TOKEN_TTL,
            )
            _send_confirmation(user.email, raw_token)
    except ValidationError as exc:
        _raise_or_hide(exc)
    except IntegrityError as exc:
        name = _constraint_name(exc)
        if name == _ALIAS_CONSTRAINT:
            raise RegistrationError({"alias": ["Ese alias ya está en uso."]}) from exc
        if name == _EMAIL_CONSTRAINT:
            return
        raise


def confirm_email(raw_token: str) -> None:
    if not raw_token:
        raise InvalidConfirmation
    with transaction.atomic():
        row = (
            EmailVerification.objects.select_for_update(of=("self",))
            .select_related("user")
            .filter(token_hash=_digest(raw_token))
            .first()
        )
        if row is None or row.used_at is not None or row.expires_at <= timezone.now():
            raise InvalidConfirmation
        now = timezone.now()
        row.used_at = now
        row.save(update_fields=["used_at"])
        if row.user.email_verified_at is None:
            User.objects.filter(pk=row.user_id, email_verified_at__isnull=True).update(
                email_verified_at=now
            )


def _send_confirmation(email: str, raw_token: str) -> None:
    link = f"{settings.API_ORIGIN}/api/users/verify-email?{urlencode({'token': raw_token})}"
    message = (
        "Confirma tu correo en Hex Campaign.\n\n"
        f"{link}\n\n"
        "El enlace caduca a las 24 horas y solo puede usarse una vez.\n"
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


def _raise_or_hide(exc: ValidationError) -> None:
    fields = set(getattr(exc, "message_dict", {}))
    if "email" in fields:
        return
    if "alias_taken" in _error_codes(exc) or "alias" in fields:
        raise RegistrationError({"alias": ["Ese alias ya está en uso."]}) from exc
    if fields:
        raise RegistrationError(
            {key: list(value) for key, value in exc.message_dict.items()}
        ) from exc
    raise RegistrationError({"email": ["No se ha podido crear la cuenta."]}) from exc
