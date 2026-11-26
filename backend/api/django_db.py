"""Close stale Django connections around a sync FastAPI view."""

from functools import wraps

from django.db import close_old_connections


def django_sync(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        close_old_connections()
        try:
            return view(*args, **kwargs)
        finally:
            close_old_connections()

    return wrapper
