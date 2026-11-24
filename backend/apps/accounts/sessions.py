"""Player login.

The cookie is a 256-bit random value. The database stores an HMAC of it, so a
copy of the table is not enough to wear the session. A campaign is not part of
the session: the same login can play every campaign, and the campaign stays
when the cookie expires.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import PlayerSession, User
from .passwords import check_encoded_password, check_user_password, dummy_password_hash
from .throttle import login_emails
from .validation import MAX_PASSWORD_LENGTH, canonical_email

# token_urlsafe(32) is 43 characters. A longer cookie is never one we issued.
MAX_SECRET_LENGTH = 128


class LoginRejected(Exception):
    """The email, the password, or the account state did not pass. Same result."""


class LoginThrottled(Exception):
    pass


@dataclass(frozen=True)
class OpenedSession:
    token: str
    csrf_token: str
    max_age: int
    user: User


def session_digest(raw: str, *, purpose: str) -> str:
    pepper = settings.SESSION_PEPPER
    if not isinstance(pepper, str) or len(pepper) < 50:
        raise ImproperlyConfigured("SESSION_PEPPER must be at least 50 characters.")
    return hmac.new(
        pepper.encode(),
        f"{purpose}\0{raw}".encode(),
        hashlib.sha256,
    ).hexdigest()


def login(email: object, password: object) -> OpenedSession:
    if not _email_attempt_allowed(email):
        raise LoginThrottled
    user = _authenticated_user(email, password)
    if user is None:
        raise LoginRejected
    return open_session(user)


def open_session(user: User) -> OpenedSession:
    authenticated_hash = user.password
    last_error: IntegrityError | None = None
    for _ in range(2):
        try:
            return _insert_session(user, authenticated_hash)
        except IntegrityError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def load_session(raw_token: str, *, touch: bool = True) -> PlayerSession | None:
    if not raw_token or len(raw_token) > MAX_SECRET_LENGTH:
        return None
    session = (
        PlayerSession.objects.select_related("user")
        .filter(token_hash=session_digest(raw_token, purpose="session"))
        .first()
    )
    if session is None:
        return None
    now = timezone.now()
    user = session.user
    idle_deadline = session.last_seen_at + timedelta(seconds=settings.SESSION_IDLE_SECONDS)
    if (
        session.expires_at <= now
        or idle_deadline <= now
        or not user.is_active
        or user.email_verified_at is None
    ):
        session.delete()
        return None
    if touch and session.last_seen_at + timedelta(seconds=settings.SESSION_TOUCH_SECONDS) <= now:
        session.last_seen_at = now
        session.save(update_fields=["last_seen_at"])
    return session


def csrf_matches(session: PlayerSession, header: str, cookie: str) -> bool:
    if (
        not header
        or not cookie
        or len(header) > MAX_SECRET_LENGTH
        or len(cookie) > MAX_SECRET_LENGTH
        or len(header) != len(cookie)
    ):
        return False
    if not hmac.compare_digest(header, cookie):
        return False
    return hmac.compare_digest(session_digest(header, purpose="csrf"), session.csrf_hash)


def _email_attempt_allowed(email: object) -> bool:
    if isinstance(email, str):
        key = canonical_email(email)[:254] or "-"
    else:
        key = "-"
    return login_emails.allow(
        key,
        settings.LOGIN_EMAIL_LIMIT,
        settings.LOGIN_EMAIL_WINDOW_SECONDS,
    )


def _authenticated_user(email: object, password: object) -> User | None:
    # A huge password is rejected before Argon2 so it cannot pin the process.
    if not isinstance(password, str) or len(password) > MAX_PASSWORD_LENGTH:
        return None
    user = _find_user(email)
    if user is None:
        check_encoded_password(password, dummy_password_hash())
        return None
    if not check_user_password(user, password):
        return None
    if not user.is_active or user.email_verified_at is None:
        return None
    return user


def _find_user(email: object) -> User | None:
    if not isinstance(email, str):
        return None
    canonical = canonical_email(email)
    if not canonical or len(canonical) > 254:
        return None
    return User.objects.filter(email=canonical).first()


def _insert_session(user: User, authenticated_hash: str) -> OpenedSession:
    raw = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = timezone.now()
    expires_at = now + timedelta(seconds=settings.SESSION_ABSOLUTE_SECONDS)
    with transaction.atomic():
        try:
            locked = User.objects.select_for_update().get(pk=user.pk)
        except User.DoesNotExist:
            raise LoginRejected from None
        if (
            locked.password != authenticated_hash
            or not locked.is_active
            or locked.email_verified_at is None
        ):
            raise LoginRejected
        limit = settings.SESSION_MAX_PER_USER
        if limit < 1:
            raise ImproperlyConfigured("SESSION_MAX_PER_USER must be at least 1.")
        existing = list(
            PlayerSession.objects.filter(user=locked)
            .order_by("-last_seen_at", "-pk")
            .values_list("pk", flat=True)
        )
        extra = existing[limit - 1 :]
        if extra:
            PlayerSession.objects.filter(pk__in=extra).delete()
        PlayerSession.objects.create(
            user=locked,
            token_hash=session_digest(raw, purpose="session"),
            csrf_hash=session_digest(csrf, purpose="csrf"),
            last_seen_at=now,
            expires_at=expires_at,
        )
    return OpenedSession(
        token=raw,
        csrf_token=csrf,
        max_age=max(int((expires_at - timezone.now()).total_seconds()), 0),
        user=locked,
    )


# Built at import so the first unknown email does not do two hashes.
dummy_password_hash()
