"""Close stale Django connections around a sync FastAPI view."""

from collections.abc import Callable
from functools import wraps

from django.db import close_old_connections


def django_sync[**P, R](view: Callable[P, R]) -> Callable[P, R]:
    @wraps(view)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        close_old_connections()
        try:
            return view(*args, **kwargs)
        finally:
            close_old_connections()

    return wrapper
