"""Password reset. The response never says whether the email exists."""

import hashlib
import logging
import secrets
from datetime import timedelta
from smtplib import SMTPException
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone, translation

from .languages import normalize, reset_mail
from .models import PasswordReset, User
from .passwords import set_user_password
from .validation import MAX_PASSWORD_LENGTH, PASSWORD_TOO_LONG, canonical_email

log = logging.getLogger("hexcampaign.mail")

RESET_TTL = timedelta(hours=2)
ACCEPTED_DETAIL = "Si el correo está registrado, te enviaremos un enlace."


class ResetRejected(Exception):
    def __init__(self, errors: dict[str, list[str]]) -> None:
        self.errors = errors
        super().__init__(errors)


class InvalidReset(Exception):
    pass


class ResetMailError(Exception):
    pass


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def request_reset(email: object, language: str = "es") -> None:
    """Send a link when the account is confirmed and active. Otherwise stay quiet."""
    language = normalize(language if isinstance(language, str) else None)
    if not isinstance(email, str):
        return
    canonical = canonical_email(email)
    if not canonical or len(canonical) > 254:
        return
    user = User.objects.filter(
        email=canonical,
        is_active=True,
        email_verified_at__isnull=False,
    ).first()
    if user is None:
        return
    raw = secrets.token_urlsafe(32)
    with transaction.atomic():
        PasswordReset.objects.filter(user=user, used_at__isnull=True).delete()
        PasswordReset.objects.create(
            user=user,
            token_hash=_digest(raw),
            expires_at=timezone.now() + RESET_TTL,
        )
    link = f"{settings.API_ORIGIN}/api/password-reset/confirm?{urlencode({'token': raw})}"
    subject, message = reset_mail(language, link)
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except (OSError, SMTPException) as exc:
        log.exception("password reset mail was not accepted")
        raise ResetMailError from exc


def password_errors(password: object) -> list[str]:
    if not isinstance(password, str):
        return ["La contraseña no es válida."]
    if len(password) > MAX_PASSWORD_LENGTH:
        return [PASSWORD_TOO_LONG]
    try:
        with translation.override("es"):
            validate_password(password)
    except ValidationError as exc:
        return list(exc.messages)
    return []


def reset_password(raw_token: object, password: object) -> None:
    if not isinstance(raw_token, str) or not raw_token or len(raw_token) > 128:
        raise InvalidReset
    errors = password_errors(password)
    if errors:
        raise ResetRejected({"password": errors})
    if not isinstance(password, str):
        raise ResetRejected({"password": ["La contraseña no es válida."]})
    digest = _digest(raw_token)
    with transaction.atomic():
        row = (
            PasswordReset.objects.select_for_update()
            .select_related("user")
            .filter(token_hash=digest)
            .first()
        )
        if row is None or row.used_at is not None or row.expires_at <= timezone.now():
            raise InvalidReset
        user = User.objects.select_for_update().filter(pk=row.user_id).first()
        if user is None or not user.is_active or user.email_verified_at is None:
            raise InvalidReset
        set_user_password(user, password)
        user.save()
        row.used_at = timezone.now()
        row.save(update_fields=["used_at"])
        PasswordReset.objects.filter(user=user, used_at__isnull=True).delete()
