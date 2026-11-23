"""Account rules shared by the model and registration."""

import re
from datetime import date

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils import translation

ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,24}\Z")
MINIMUM_AGE_YEARS = 16
SEX_VALUES = ("woman", "man", "other", "undisclosed")

_EMAIL = EmailValidator(message="Introduce un correo válido.")


def age_on(born: date, on: date) -> int:
    years = on.year - born.year
    if (on.month, on.day) < (born.month, born.day):
        years -= 1
    return years


def registration_errors(
    *,
    email: str,
    password: str,
    alias: str,
    birth_date: date,
    sex: str,
    today: date,
) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    try:
        _EMAIL(email.strip())
    except ValidationError as exc:
        errors["email"] = list(exc.messages)

    cleaned_alias = alias.strip()
    if not ALIAS_PATTERN.fullmatch(cleaned_alias):
        errors["alias"] = ["El alias usa de 3 a 24 letras, números o guion bajo."]

    if age_on(birth_date, today) < MINIMUM_AGE_YEARS:
        errors["birth_date"] = ["Hay que tener al menos 16 años."]

    if sex not in SEX_VALUES:
        errors["sex"] = ["Elige woman, man, other o undisclosed."]

    try:
        with translation.override("es"):
            validate_password(password)
    except ValidationError as exc:
        errors["password"] = list(exc.messages)
    return errors
