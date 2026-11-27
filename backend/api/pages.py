"""HTML for the confirmation link. The token is not consumed until the button is posted."""

from html import escape
from urllib.parse import quote

from apps.accounts.languages import LANGUAGE_NAMES, LANGUAGES, normalize, phrase, present


def _document(language: str, title: str, body: str) -> str:
    lang = escape(language, quote=True)
    return (
        "<!DOCTYPE html>"
        f'<html lang="{lang}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex">'
        '<meta name="referrer" content="no-referrer">'
        f"<title>{escape(title)}</title></head>"
        f"<body><main>{body}</main></body></html>"
    )


def _languages(token: str, language: str) -> str:
    hidden = quote(token, safe="")
    links = []
    for code in LANGUAGES:
        href = f"?token={hidden}&amp;lang={code}"
        name = escape(LANGUAGE_NAMES[code])
        current = ' aria-current="true"' if code == language else ""
        links.append(f'<a href="{href}" lang="{code}" hreflang="{code}"{current}>{name}</a>')
    label = escape(phrase(language, "language"))
    return f'<p align="right">{label}: {" ".join(links)}</p>'


def confirm_page(token: str, error: str = "", language: str = "es") -> str:
    language = normalize(language)
    hidden = escape(token, quote=True)
    lang = escape(language, quote=True)
    notice = f"<p>{escape(present(language, error))}</p>" if error else ""
    body = (
        f"{_languages(token, language)}"
        f"{notice}"
        f"<p>{escape(phrase(language, 'confirm_lead'))}</p>"
        '<form method="post" action="/api/users/verify-email">'
        f'<input type="hidden" name="token" value="{hidden}">'
        f'<input type="hidden" name="lang" value="{lang}">'
        f"<label>{escape(phrase(language, 'password'))} "
        '<input type="password" name="password" '
        'autocomplete="current-password" maxlength="128" required></label>'
        f"<button type=\"submit\">{escape(phrase(language, 'confirm_button'))}</button>"
        "</form>"
    )
    return _document(language, phrase(language, "confirm_title"), body)


def reset_page(token: str, error: str = "", language: str = "es") -> str:
    language = normalize(language)
    hidden = escape(token, quote=True)
    lang = escape(language, quote=True)
    notice = f"<p>{escape(present(language, error))}</p>" if error else ""
    body = (
        f"{notice}"
        f"<p>{escape(phrase(language, 'reset_lead'))}</p>"
        '<form method="post" action="/api/password-reset/confirm">'
        f'<input type="hidden" name="token" value="{hidden}">'
        f'<input type="hidden" name="lang" value="{lang}">'
        f"<label>{escape(phrase(language, 'password'))} "
        '<input type="password" name="password" '
        'autocomplete="new-password" minlength="12" maxlength="128" required></label>'
        f"<button type=\"submit\">{escape(phrase(language, 'reset_button'))}</button>"
        "</form>"
    )
    return _document(language, phrase(language, "reset_title"), body)


def result_page(message: str, language: str = "es") -> str:
    language = normalize(language)
    shown = present(language, message)
    body = f"<p>{escape(shown)}</p>"
    return _document(language, phrase(language, "result_title"), body)
