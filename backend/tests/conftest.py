"""Fixtures that know the required profile on a user."""

from datetime import date

import pytest


@pytest.fixture
def admin_user(db, django_user_model):
    return django_user_model.objects.create_superuser(
        "admin@example.com",
        "clave-de-admin-larga",
        alias="admin_root",
        birth_date=date(1990, 1, 1),
        sex="undisclosed",
    )
