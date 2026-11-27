"""Argon2 holds a large memory block, so only two hashes run at once."""

import threading

from django.contrib.auth.hashers import check_password, make_password

_HASH_SLOTS = threading.Semaphore(2)
_DUMMY_PASSWORD = "player-login-dummy-not-a-password"  # noqa: S105
_dummy_hash: str | None = None


class HashBusy(Exception):
    """Both Argon2 slots are taken. The caller should answer 429, not wait."""


def _acquire(*, wait: float) -> None:
    if not _HASH_SLOTS.acquire(timeout=wait):
        raise HashBusy


def set_user_password(user, password: str) -> None:
    _acquire(wait=2)
    try:
        user.set_password(password)
    finally:
        _HASH_SLOTS.release()


def check_user_password(user, password: str) -> bool:
    # Login must not sit in the thread pool behind a queue of hashes.
    _acquire(wait=0)
    try:
        return user.check_password(password)
    finally:
        _HASH_SLOTS.release()


def check_encoded_password(password: str, encoded: str) -> bool:
    _acquire(wait=0)
    try:
        return check_password(password, encoded)
    finally:
        _HASH_SLOTS.release()


def dummy_password_hash() -> str:
    """A real Argon2 hash so an unknown email costs the same work as a real one."""
    global _dummy_hash
    if _dummy_hash is not None:
        return _dummy_hash
    with _HASH_SLOTS:
        if _dummy_hash is None:
            _dummy_hash = make_password(_DUMMY_PASSWORD)
        return _dummy_hash
