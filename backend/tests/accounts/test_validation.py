"""Account rules shared by the model and registration."""

from datetime import date

import pytest

from apps.accounts.validation import (
    ALIAS_MESSAGE,
    MINIMUM_AGE_YEARS,
    SEX_MESSAGE,
    Sex,
    age_on,
    alias_errors,
    birth_date_errors,
    canonical_alias,
    canonical_email,
    registration_errors,
)

TODAY = date(2026, 11, 23)


def test_canonical_forms_keep_alias_case_and_lower_the_email() -> None:
    assert canonical_email("  Ada@Example.com ") == "ada@example.com"
    assert canonical_alias("  Ada_Lovelace ") == "Ada_Lovelace"


def test_age_changes_on_the_birthday() -> None:
    born = date(2000, 11, 23)

    assert age_on(born, date(2016, 11, 22)) == 15
    assert age_on(born, date(2016, 11, 23)) == 16
    assert age_on(born, date(2016, 11, 24)) == 16


def test_february_29_advances_on_march_1_in_a_non_leap_year() -> None:
    born = date(2008, 2, 29)

    assert age_on(born, date(2009, 2, 28)) == 0
    assert age_on(born, date(2009, 3, 1)) == 1


@pytest.mark.parametrize("alias", ["abc", "a" * 24, "A_b3", "___"])
def test_alias_shape_accepts_letters_digits_and_underscore(alias: str) -> None:
    assert alias_errors(alias) == {}


@pytest.mark.parametrize("alias", ["", "ab", "a" * 25, "a-b", "a b", "ábc", "ab.c"])
def test_alias_shape_rejects_anything_else(alias: str) -> None:
    assert alias_errors(alias) == {"alias": [ALIAS_MESSAGE]}


def test_birth_date_requires_the_minimum_age() -> None:
    assert birth_date_errors(date(2010, 11, 23), TODAY) == {}

    errors = birth_date_errors(date(2010, 11, 24), TODAY)

    assert errors == {"birth_date": [f"Hay que tener al menos {MINIMUM_AGE_YEARS} años."]}


def test_registration_reports_every_invalid_field() -> None:
    errors = registration_errors(
        email="no-es-correo",
        password="corta",
        alias="!!",
        birth_date=date(2020, 1, 1),
        sex="Woman",
        today=TODAY,
    )

    assert set(errors) == {"email", "password", "alias", "birth_date", "sex"}
    assert errors["email"] == ["Introduce un correo válido."]
    assert errors["alias"] == [ALIAS_MESSAGE]
    assert errors["birth_date"] == [f"Hay que tener al menos {MINIMUM_AGE_YEARS} años."]
    assert errors["sex"] == [SEX_MESSAGE]
    assert "12" in errors["password"][0]


def test_registration_accepts_a_twelve_character_password() -> None:
    errors = registration_errors(
        email=" ada@example.com ",
        password="123456789012",
        alias=" ada ",
        birth_date=date(1990, 1, 1),
        sex=Sex.UNDISCLOSED,
        today=TODAY,
    )

    assert errors == {}


def test_eleven_characters_is_too_short() -> None:
    errors = registration_errors(
        email="ada@example.com",
        password="12345678901",
        alias="ada",
        birth_date=date(1990, 1, 1),
        sex=Sex.MAN,
        today=TODAY,
    )

    assert set(errors) == {"password"}
    assert "12" in errors["password"][0]


def test_canonical_forms_fold_compat_characters() -> None:
    assert canonical_email("\uff21da@example.com") == "ada@example.com"
    assert canonical_alias("\uff41bc") == "abc"
    assert alias_errors(canonical_alias("\uff41bc")) == {}


def test_password_and_email_have_a_maximum_length() -> None:
    long_password = registration_errors(
        email="ada@example.com",
        password="a" * 129,
        alias="ada",
        birth_date=date(1990, 1, 1),
        sex=Sex.WOMAN,
        today=TODAY,
    )
    assert long_password == {"password": ["La contraseña admite como máximo 128 caracteres."]}

    accepted = registration_errors(
        email="ada@example.com",
        password="a" * 128,
        alias="ada",
        birth_date=date(1990, 1, 1),
        sex=Sex.WOMAN,
        today=TODAY,
    )
    assert accepted == {}

    long_email = registration_errors(
        email="a" * 250 + "@example.com",
        password="una-clave-larga",
        alias="ada",
        birth_date=date(1990, 1, 1),
        sex=Sex.WOMAN,
        today=TODAY,
    )
    assert long_email["email"] == ["Introduce un correo válido."]


def test_sex_codes_and_labels() -> None:
    assert Sex.WOMAN.label == "Mujer"
    assert Sex.MAN.label == "Hombre"
    assert Sex.OTHER.label == "Otro"
    assert Sex.UNDISCLOSED.label == "Prefiero no decirlo"
    assert list(Sex.values) == ["woman", "man", "other", "undisclosed"]
    assert SEX_MESSAGE == "Elige woman, man, other o undisclosed."
