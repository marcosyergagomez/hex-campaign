"""Argon2 holds a large memory block, so only two hashes run at once."""

import threading

from django.contrib.auth.hashers import check_password, make_password

_HASH_SLOTS = threading.Semaphore(2)
_DUMMY_PASSWORD = "player-login-dummy-not-a-password"
_dummy_hash: str | None = None


def set_user_password(user, password: str) -> None:
    with _HASH_SLOTS:
        user.set_password(password)


def check_user_password(user, password: str) -> bool:
    with _HASH_SLOTS:
        return user.check_password(password)


def check_encoded_password(password: str, encoded: str) -> bool:
    with _HASH_SLOTS:
        return check_password(password, encoded)


def dummy_password_hash() -> str:
    """A real Argon2 hash so an unknown email costs the same work as a real one."""
    global _dummy_hash
    if _dummy_hash is not None:
        return _dummy_hash
    with _HASH_SLOTS:
        if _dummy_hash is None:
            _dummy_hash = make_password(_DUMMY_PASSWORD)
        return _dummy_hash
