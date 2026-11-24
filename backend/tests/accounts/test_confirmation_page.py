"""The confirmation page posts the token and does not consume it."""

from api.pages import confirm_page, result_page


def test_confirm_page_escapes_the_token_and_posts_it() -> None:
    page = confirm_page('"><script>')

    assert 'lang="es"' in page
    assert 'content="noindex"' in page
    assert 'content="no-referrer"' in page
    assert 'action="/api/users/verify-email"' in page
    assert 'value="&quot;&gt;&lt;script&gt;"' in page
    assert "<script>" not in page
    assert "Confirmar correo" in page
    assert 'type="password"' in page
    assert 'name="password"' in page


def test_result_page_escapes_the_message() -> None:
    page = result_page("<b>listo</b>")

    assert "&lt;b&gt;listo&lt;/b&gt;" in page
    assert "<b>" not in page


def test_confirm_page_can_be_shown_in_german() -> None:
    page = confirm_page("token", language="de")

    assert 'lang="de"' in page
    assert "E-Mail bestätigen" in page
    assert "Confirmar correo" not in page
    assert "lang=de" in page
    assert "English" in page
    assert "<script>" not in page
