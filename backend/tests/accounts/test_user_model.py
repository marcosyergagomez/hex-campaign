"""Profile rules live on the user row."""

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.formats import get_format

from apps.accounts.models import EmailVerification, Sex, User
from apps.accounts.validation import SEX_MESSAGE

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
    assert user.is_active is True
    assert user.is_staff is False
    assert user.created_at is not None
    assert user.password.startswith("argon2")
    assert user.check_password("una-clave-larga")
    assert str(user) == "Ada_Lovelace"


@pytest.mark.django_db
def test_email_and_alias_ignore_case() -> None:
    _create()

    with pytest.raises(ValidationError) as email_error:
        _create(email="ADA@example.com", alias="otra_persona")
    assert "email" in email_error.value.message_dict
    with pytest.raises(ValidationError) as alias_error:
        _create(email="otro@example.com", alias="ADA_LOVELACE")
    assert alias_error.value.message_dict["__all__"] == ["Ese alias ya está en uso."]
    assert alias_error.value.error_dict["__all__"][0].code == "alias_taken"


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
    assert "Mujer" in body
    assert "Hombre" in body
    assert "Otro" in body
    assert "Prefiero no decirlo" in body


def test_string_form_falls_back_to_the_email() -> None:
    assert str(User(email="ada@example.com", alias="")) == "ada@example.com"


@pytest.mark.django_db
def test_manager_rejects_a_blank_email_and_a_demoted_superuser() -> None:
    with pytest.raises(ValueError, match="An email is required."):
        User.objects.create_user(
            "  ",
            "una-clave-larga",
            alias="sin_correo",
            birth_date=BORN,
            sex=Sex.MAN,
        )
    with pytest.raises(ValueError, match="is_staff and is_superuser"):
        User.objects.create_superuser(
            "root@example.com",
            "clave-de-admin-larga",
            alias="root_user",
            birth_date=BORN,
            sex=Sex.UNDISCLOSED,
            is_staff=False,
        )
    with pytest.raises(ValueError, match="is_staff and is_superuser"):
        User.objects.create_superuser(
            "root@example.com",
            "clave-de-admin-larga",
            alias="root_user",
            birth_date=BORN,
            sex=Sex.UNDISCLOSED,
            is_superuser=False,
        )

    admin = User.objects.create_superuser(
        "root@example.com",
        "clave-de-admin-larga",
        alias="root_user",
        birth_date=BORN,
        sex=Sex.UNDISCLOSED,
    )
    assert admin.is_staff is True
    assert admin.is_superuser is True


@pytest.mark.django_db
@pytest.mark.parametrize("sex", list(Sex.values))
def test_every_sex_code_is_stored(sex: str) -> None:
    user = _create(email=f"{sex}@example.com", alias=f"sexo_{sex}", sex=sex)

    assert user.sex == sex


@pytest.mark.django_db
def test_alias_bounds_and_unknown_sex() -> None:
    assert _create(email="tres@example.com", alias="abc").alias == "abc"
    assert _create(email="largo@example.com", alias="b" * 24).alias == "b" * 24

    with pytest.raises(ValidationError) as too_long:
        _create(email="mas@example.com", alias="c" * 25)
    assert "alias" in too_long.value.message_dict

    with pytest.raises(ValidationError) as hyphen:
        _create(email="guion@example.com", alias="a-b")
    assert "alias" in hyphen.value.message_dict

    with pytest.raises(ValidationError) as sex:
        _create(email="sexo@example.com", alias="sexo_malo", sex="nope")
    assert sex.value.message_dict["sex"] == [SEX_MESSAGE]

    tomorrow = timezone.localdate() + timedelta(days=1)
    with pytest.raises(ValidationError) as future:
        _create(email="futuro@example.com", alias="aun_no", birth_date=tomorrow)
    assert "16" in future.value.message_dict["birth_date"][0]


@pytest.mark.django_db
def test_database_checks_alias_shape_and_sex() -> None:
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.bulk_create(
                [
                    User(
                        email="forma@example.com",
                        alias="ab",
                        birth_date=BORN,
                        sex=Sex.WOMAN,
                        password="x",
                    )
                ]
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.bulk_create(
                [
                    User(
                        email="sexo@example.com",
                        alias="sexo_malo",
                        birth_date=BORN,
                        sex="nope",
                        password="x",
                    )
                ]
            )


@pytest.mark.django_db
def test_confirmation_row_is_unique_and_follows_the_user() -> None:
    user = _create()
    expires = timezone.now() + timedelta(hours=24)
    row = EmailVerification.objects.create(
        user=user,
        token_hash="a" * 64,
        expires_at=expires,
    )
    assert str(row) == f"{user.pk} {row.expires_at:%Y-%m-%d}"

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailVerification.objects.create(
                user=user,
                token_hash="a" * 64,
                expires_at=expires,
            )

    user.delete()
    assert EmailVerification.objects.count() == 0


def _admin_date(day: date) -> str:
    return day.strftime(get_format("DATE_INPUT_FORMATS")[0])


@pytest.mark.django_db
def test_admin_stores_a_valid_account_and_rejects_a_young_one(admin_client) -> None:
    today = timezone.localdate()
    young = admin_client.post(
        "/admin/accounts/user/add/",
        {
            "email": "joven@example.com",
            "alias": "casi_dieciseis",
            "birth_date": _admin_date(_years_ago(today, 16) + timedelta(days=1)),
            "sex": Sex.MAN,
            "password1": "una-clave-larga",
            "password2": "una-clave-larga",
        },
    )
    assert young.status_code == 200
    assert User.objects.filter(email="joven@example.com").count() == 0
    assert "16" in young.content.decode()

    created = admin_client.post(
        "/admin/accounts/user/add/",
        {
            "email": "Nuevo@Example.com",
            "alias": "Nuevo_Alias",
            "birth_date": _admin_date(BORN),
            "sex": Sex.MAN,
            "password1": "una-clave-larga",
            "password2": "una-clave-larga",
        },
    )
    assert created.status_code == 302, created.content.decode()[:1500]
    user = User.objects.get(email="nuevo@example.com")
    assert user.alias == "Nuevo_Alias"
    assert user.sex == Sex.MAN
    assert user.check_password("una-clave-larga")

    change = admin_client.get(f"/admin/accounts/user/{user.pk}/change/")
    assert change.status_code == 200
    body = change.content.decode()
    assert "id_birth_date" in body
    assert "id_sex" in body
    assert "id_email_verified_at" in body

    listed = admin_client.get("/admin/accounts/user/", {"q": "Nuevo_Alias"})
    assert "nuevo@example.com" in listed.content.decode()
    missing = admin_client.get("/admin/accounts/user/", {"q": "nadie_aqui"})
    assert "nuevo@example.com" not in missing.content.decode()
