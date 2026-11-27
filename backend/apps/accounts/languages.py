"""Wording for the confirmation mail and its page.

The JSON API stays in Spanish. These texts follow the language cookie the
browser sends, and fall back to Spanish when it is missing or unknown.
"""

from typing import Literal, cast

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
        "reset_subject": "Reset your password",
        "reset_intro": "Reset your Hex Campaign password.",
        "reset_expires": "The link expires in 2 hours and can be used only once.",
        "reset_ignore": "If you did not ask to reset your password, ignore this message.",
        "reset_title": "New password",
        "reset_lead": "Choose a new password of 12 to 128 characters.",
        "reset_button": "Save password",
        "reset_done": "Password updated. You can sign in.",
        "password_invalid": "The password is not valid.",
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
        "reset_subject": "Restablece tu contraseña",
        "reset_intro": "Restablece tu contraseña de Hex Campaign.",
        "reset_expires": "El enlace caduca a las 2 horas y solo puede usarse una vez.",
        "reset_ignore": "Si no has pedido restablecer la contraseña, ignora este mensaje.",
        "reset_title": "Nueva contraseña",
        "reset_lead": "Elige una contraseña nueva de 12 a 128 caracteres.",
        "reset_button": "Guardar contraseña",
        "reset_done": "Contraseña actualizada. Ya puedes entrar.",
        "password_invalid": "La contraseña no es válida.",
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
        "reset_subject": "Réinitialise ton mot de passe",
        "reset_intro": "Réinitialise ton mot de passe Hex Campaign.",
        "reset_expires": "Le lien expire au bout de 2 heures et ne peut servir qu'une fois.",
        "reset_ignore": "Si tu n'as pas demandé cette réinitialisation, ignore ce message.",
        "reset_title": "Nouveau mot de passe",
        "reset_lead": "Choisis un mot de passe de 12 à 128 caractères.",
        "reset_button": "Enregistrer le mot de passe",
        "reset_done": "Mot de passe mis à jour. Tu peux entrer.",
        "password_invalid": "Le mot de passe n'est pas valide.",
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
        "reset_subject": "Reimposta la password",
        "reset_intro": "Reimposta la password di Hex Campaign.",
        "reset_expires": "Il link scade dopo 2 ore e si può usare una sola volta.",
        "reset_ignore": "Se non hai chiesto di reimpostare la password, ignora questo messaggio.",
        "reset_title": "Nuova password",
        "reset_lead": "Scegli una password di 12-128 caratteri.",
        "reset_button": "Salva la password",
        "reset_done": "Password aggiornata. Ora puoi entrare.",
        "password_invalid": "La password non è valida.",
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
        "reset_subject": "Passwort zurücksetzen",
        "reset_intro": "Setze dein Hex-Campaign-Passwort zurück.",
        "reset_expires": "Der Link läuft nach 2 Stunden ab und gilt nur einmal.",
        "reset_ignore": (
            "Wenn du das Zurücksetzen nicht angefordert hast, ignoriere diese Nachricht."
        ),
        "reset_title": "Neues Passwort",
        "reset_lead": "Wähle ein Passwort mit 12 bis 128 Zeichen.",
        "reset_button": "Passwort speichern",
        "reset_done": "Passwort aktualisiert. Du kannst dich anmelden.",
        "password_invalid": "Das Passwort ist ungültig.",
    },
}

_FROM_SPANISH = {
    "El enlace no es válido o ha caducado.": "invalid_link",
    "Correo confirmado.": "confirmed",
    "La contraseña no coincide.": "password_mismatch",
    "La contraseña no es válida.": "password_invalid",
    "Contraseña actualizada. Ya puedes entrar.": "reset_done",
}


def normalize(value: str | None) -> Language:
    if value in {"en", "es", "fr", "it", "de"}:
        return cast(Language, value)
    return "es"


def phrase(language: str | None, key: str) -> str:
    return _CATALOG[normalize(language)][key]


def present(language: str | None, message: str) -> str:
    key = _FROM_SPANISH.get(message)
    if key is None:
        return message
    return phrase(language, key)


def reset_mail(language: str | None, link: str) -> tuple[str, str]:
    subject = phrase(language, "reset_subject")
    body = "\n".join(
        (
            phrase(language, "reset_intro"),
            "",
            link,
            "",
            phrase(language, "reset_expires"),
            phrase(language, "reset_ignore"),
            "",
        )
    )
    return subject, body


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
