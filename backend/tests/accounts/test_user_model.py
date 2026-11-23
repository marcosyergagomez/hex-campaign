"""Profile rules live on the user row."""

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import Sex, User

BORN = date(1990, 1, 1)


def _create(**overrides: object) -> User:
    fields: dict[str, object] = {
        "email": "ada@example.com",
        "password": "una-clave-larga",
        "alias": "ada_lovelace",
        "birth_date": BORN,
        "sex": Sex.WOMAN,
    }
    fields.update(overrides)
    return User.objects.create_user(
        str(fields.pop("email")),
        str(fields.pop("password")),
        **fields,
    )


@pytest.mark.django_db
def test_user_stores_profile_and_canonical_email() -> None:
    user = _create(email="  Ada@Example.com ", alias="  Ada_Lovelace ")

    assert user.email == "ada@example.com"
    assert user.alias == "Ada_Lovelace"
    assert user.birth_date == BORN
    assert user.sex == Sex.WOMAN
    assert user.email_verified_at is None


@pytest.mark.django_db
def test_email_and_alias_ignore_case() -> None:
    _create()

    with pytest.raises(ValidationError):
        _create(email="ADA@example.com", alias="otra_persona")
    with pytest.raises(ValidationError):
        _create(email="otro@example.com", alias="ADA_LOVELACE")


def _years_ago(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


@pytest.mark.django_db
def test_alias_shape_and_minimum_age() -> None:
    with pytest.raises(ValidationError) as too_short:
        _create(alias="ab")
    assert "alias" in too_short.value.message_dict

    today = timezone.localdate()
    almost_sixteen = _years_ago(today, 16) + timedelta(days=1)
    with pytest.raises(ValidationError) as too_young:
        _create(email="joven@example.com", alias="casi_dieciseis", birth_date=almost_sixteen)
    assert "birth_date" in too_young.value.message_dict

    user = _create(
        email="mayor@example.com",
        alias="justo_dieciseis",
        birth_date=_years_ago(today, 16),
    )
    assert user.birth_date == _years_ago(today, 16)


@pytest.mark.django_db
def test_admin_create_user_asks_for_the_profile(admin_client) -> None:
    response = admin_client.get("/admin/accounts/user/add/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "id_alias" in body
    assert "id_birth_date" in body
    assert "id_sex" in body
