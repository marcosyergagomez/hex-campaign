"""HTML for the confirmation link. The token is not consumed until the button is posted."""

from html import escape


def _document(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>"
        '<html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex">'
        '<meta name="referrer" content="no-referrer">'
        f"<title>{title}</title></head>"
        f"<body><main><h1>Hex Campaign</h1>{body}</main></body></html>"
    )


def confirm_page(token: str, error: str = "") -> str:
    hidden = escape(token, quote=True)
    notice = f"<p>{escape(error)}</p>" if error else ""
    body = (
        f"{notice}"
        "<p>Escribe la contraseña del alta y pulsa el botón para confirmar tu correo.</p>"
        '<form method="post" action="/api/users/verify-email">'
        f'<input type="hidden" name="token" value="{hidden}">'
        '<label>Contraseña <input type="password" name="password" '
        'autocomplete="current-password" maxlength="128" required></label>'
        '<button type="submit">Confirmar correo</button>'
        "</form>"
    )
    return _document("Confirmar correo", body)


def result_page(message: str) -> str:
    return _document("Correo", f"<p>{escape(message)}</p>")
