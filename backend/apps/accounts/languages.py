"""Wording for the confirmation mail and its page.

The JSON API stays in Spanish. These texts follow the language cookie the
browser sends, and fall back to Spanish when it is missing or unknown.
"""

from typing import Literal

Language = Literal["en", "es", "fr", "it", "de"]
LANGUAGES: tuple[Language, ...] = ("en", "es", "fr", "it", "de")

LANGUAGE_NAMES: dict[Language, str] = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "de": "Deutsch",
}

_Copy = dict[str, str]

_CATALOG: dict[Language, _Copy] = {
    "en": {
        "email_subject": "Confirm your email",
        "email_intro": "Confirm your email for Hex Campaign.",
        "email_expires": "The link expires in 24 hours and can be used only once.",
        "email_password": "On the page, enter the password you chose when you registered.",
        "email_ignore": "If you did not ask for this account, ignore this message.",
        "confirm_title": "Confirm email",
        "confirm_lead": "Enter the password from registration and confirm your email.",
        "password": "Password",
        "confirm_button": "Confirm email",
        "result_title": "Email",
        "invalid_link": "The link is not valid or has expired.",
        "confirmed": "Email confirmed.",
        "password_mismatch": "The password does not match.",
        "language": "Language",
    },
    "es": {
        "email_subject": "Confirma tu correo",
        "email_intro": "Confirma tu correo en Hex Campaign.",
        "email_expires": "El enlace caduca a las 24 horas y solo puede usarse una vez.",
        "email_password": (
            "En la página tendrás que escribir la contraseña que elegiste al registrarte."
        ),
        "email_ignore": "Si no has pedido este alta, ignora este mensaje.",
        "confirm_title": "Confirmar correo",
        "confirm_lead": "Escribe la contraseña del alta y pulsa el botón para confirmar tu correo.",
        "password": "Contraseña",
        "confirm_button": "Confirmar correo",
        "result_title": "Correo",
        "invalid_link": "El enlace no es válido o ha caducado.",
        "confirmed": "Correo confirmado.",
        "password_mismatch": "La contraseña no coincide.",
        "language": "Idioma",
    },
    "fr": {
        "email_subject": "Confirme ton e-mail",
        "email_intro": "Confirme ton e-mail pour Hex Campaign.",
        "email_expires": "Le lien expire au bout de 24 heures et ne peut servir qu'une fois.",
        "email_password": "Sur la page, écris le mot de passe choisi à l'inscription.",
        "email_ignore": "Si tu n'as pas demandé cette inscription, ignore ce message.",
        "confirm_title": "Confirmer l'e-mail",
        "confirm_lead": "Écris le mot de passe de l'inscription et confirme ton e-mail.",
        "password": "Mot de passe",
        "confirm_button": "Confirmer l'e-mail",
        "result_title": "E-mail",
        "invalid_link": "Le lien n'est pas valide ou a expiré.",
        "confirmed": "E-mail confirmé.",
        "password_mismatch": "Le mot de passe ne correspond pas.",
        "language": "Langue",
    },
    "it": {
        "email_subject": "Conferma l'e-mail",
        "email_intro": "Conferma l'e-mail per Hex Campaign.",
        "email_expires": "Il link scade dopo 24 ore e si può usare una sola volta.",
        "email_password": "Nella pagina scrivi la password scelta al momento dell'iscrizione.",
        "email_ignore": "Se non hai chiesto questa iscrizione, ignora questo messaggio.",
        "confirm_title": "Conferma e-mail",
        "confirm_lead": "Scrivi la password dell'iscrizione e conferma l'e-mail.",
        "password": "Password",
        "confirm_button": "Conferma e-mail",
        "result_title": "E-mail",
        "invalid_link": "Il link non è valido oppure è scaduto.",
        "confirmed": "E-mail confermata.",
        "password_mismatch": "La password non coincide.",
        "language": "Lingua",
    },
    "de": {
        "email_subject": "Bestätige deine E-Mail",
        "email_intro": "Bestätige deine E-Mail für Hex Campaign.",
        "email_expires": "Der Link läuft nach 24 Stunden ab und gilt nur einmal.",
        "email_password": (
            "Auf der Seite gibst du das Passwort ein, das du bei der Anmeldung gewählt hast."
        ),
        "email_ignore": "Wenn du dieses Konto nicht angelegt hast, ignoriere diese Nachricht.",
        "confirm_title": "E-Mail bestätigen",
        "confirm_lead": "Gib das Passwort der Anmeldung ein und bestätige deine E-Mail.",
        "password": "Passwort",
        "confirm_button": "E-Mail bestätigen",
        "result_title": "E-Mail",
        "invalid_link": "Der Link ist ungültig oder abgelaufen.",
        "confirmed": "E-Mail bestätigt.",
        "password_mismatch": "Das Passwort stimmt nicht.",
        "language": "Sprache",
    },
}

_FROM_SPANISH = {
    "El enlace no es válido o ha caducado.": "invalid_link",
    "Correo confirmado.": "confirmed",
    "La contraseña no coincide.": "password_mismatch",
}


def normalize(value: str | None) -> Language:
    if value == "en" or value == "es" or value == "fr" or value == "it" or value == "de":
        return value
    return "es"


def phrase(language: str | None, key: str) -> str:
    return _CATALOG[normalize(language)][key]


def present(language: str | None, message: str) -> str:
    key = _FROM_SPANISH.get(message)
    if key is None:
        return message
    return phrase(language, key)


def confirmation_mail(language: str | None, link: str) -> tuple[str, str]:
    subject = phrase(language, "email_subject")
    body = "\n".join(
        (
            phrase(language, "email_intro"),
            "",
            link,
            "",
            phrase(language, "email_expires"),
            phrase(language, "email_password"),
            phrase(language, "email_ignore"),
            "",
        )
    )
    return subject, body
