"""Account rules shared by the model and registration."""

import re
import unicodedata
from datetime import date

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import models
from django.utils import translation

ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,24}\Z")
MINIMUM_AGE_YEARS = 16
MAX_EMAIL_LENGTH = 254
MAX_PASSWORD_LENGTH = 128
ALIAS_MESSAGE = "El alias usa de 3 a 24 letras, números o guion bajo."
EMAIL_TAKEN = "Este correo ya está registrado."
PASSWORD_TOO_LONG = f"La contraseña admite como máximo {MAX_PASSWORD_LENGTH} caracteres."


class Sex(models.TextChoices):
    WOMAN = "woman", "Mujer"
    MAN = "man", "Hombre"
    OTHER = "other", "Otro"
    UNDISCLOSED = "undisclosed", "Prefiero no decirlo"


SEX_MESSAGE = "Elige " + ", ".join(Sex.values[:-1]) + " o " + Sex.values[-1] + "."

_EMAIL = EmailValidator(message="Introduce un correo válido.")


def canonical_email(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().lower()


def canonical_alias(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


def age_on(born: date, on: date) -> int:
    years = on.year - born.year
    if (on.month, on.day) < (born.month, born.day):
        years -= 1
    return years


def alias_errors(alias: str) -> dict[str, list[str]]:
    if len(alias) <= 24 and ALIAS_PATTERN.fullmatch(alias):
        return {}
    return {"alias": [ALIAS_MESSAGE]}


def birth_date_errors(born: date, today: date) -> dict[str, list[str]]:
    if age_on(born, today) >= MINIMUM_AGE_YEARS:
        return {}
    return {"birth_date": [f"Hay que tener al menos {MINIMUM_AGE_YEARS} años."]}


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
    normalized = canonical_email(email)
    if len(normalized) > MAX_EMAIL_LENGTH:
        errors["email"] = ["Introduce un correo válido."]
    else:
        try:
            _EMAIL(normalized)
        except ValidationError as exc:
            errors["email"] = list(exc.messages)

    errors.update(alias_errors(canonical_alias(alias)))
    errors.update(birth_date_errors(birth_date, today))
    if sex not in Sex.values:
        errors["sex"] = [SEX_MESSAGE]

    if len(password) > MAX_PASSWORD_LENGTH:
        errors["password"] = [PASSWORD_TOO_LONG]
    else:
        try:
            with translation.override("es"):
                validate_password(password)
        except ValidationError as exc:
            errors["password"] = list(exc.messages)
    return errors
