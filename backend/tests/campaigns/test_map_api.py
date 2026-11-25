"""A saved map is copied into the campaign. Looking at it is a choice."""

from datetime import date

import pytest
from django.utils import timezone
from fastapi.testclient import TestClient

from api.player_session import CSRF_COOKIE
from apps.accounts.models import User
from apps.accounts.throttle import clear_login_limits
from config.asgi import application
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.land import rotate

PASSWORD = "una-clave-larga"
ORIGIN = "http://testserver"
RULES = {
    "seats": 2,
    "armies": 1,
    "movement": 1,
    "map_size": 19,
    "visibility": "home",
    "victory": "armies",
    "hold_turns": 3,
    "placement": "players",
    "order_days": 7,
    "battle_days": 7,
    "missed_turns": 2,
}


@pytest.fixture(autouse=True)
def _reset_login_limits():
    clear_login_limits()
    yield
    clear_login_limits()


@pytest.fixture
def clients():
    with (
        TestClient(application, base_url="https://testserver") as ana,
        TestClient(application, base_url="https://testserver") as boa,
    ):
        yield ana, boa


def _player(email: str, alias: str) -> User:
    user = User.objects.create_user(
        email,
        PASSWORD,
        alias=alias,
        birth_date=date(1990, 1, 1),
        sex="woman",
    )
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user


def _headers(client, *, write: bool) -> dict[str, str]:
    headers = {"origin": ORIGIN}
    if write:
        token = client.cookies.get(CSRF_COOKIE)
        if token:
            headers["x-csrf-token"] = token
    return headers


def _login(client, email: str) -> None:
    response = client.post(
        "/api/session",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert response.status_code == 200, response.text


def _write(client, path: str, body: dict):
    return client.post(path, json=body, headers=_headers(client, write=True))


def _read(client, path: str):
    return client.get(path, headers=_headers(client, write=False))


def _table(ana, boa, *, blind: bool, map_id: str) -> dict:
    created = _write(
        ana,
        "/api/campaigns",
        {"name": "Norte", "rules": RULES, "map_id": map_id, "blind": blind},
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    link = _write(ana, f"/api/campaigns/{campaign['id']}/links", {})
    assert link.status_code == 201, link.text
    token = link.json()["token"]
    preview = _read(boa, f"/api/invitations/{token}")
    joined = _write(
        boa,
        f"/api/invitations/{token}/accept",
        {"revision": preview.json()["revision"]},
    )
    assert joined.status_code == 200, joined.text
    started = _write(
        ana,
        f"/api/campaigns/{campaign['id']}/start",
        {"revision": joined.json()["revision"], "admins": []},
    )
    assert started.status_code == 200, started.text
    return started.json()


@pytest.mark.django_db(transaction=True)
def test_a_generated_map_stays_hidden_when_the_owner_does_not_look(clients) -> None:
    ana, boa = clients
    owner = _player("ana-map@example.com", "AnaMapa")
    _player("boa-map@example.com", "BoaMapa")
    _login(ana, owner.email)
    _login(boa, "boa-map@example.com")
    created = _write(ana, "/api/maps", {"name": "Disco", "size": 19, "seats": 2})
    assert created.status_code == 201, created.text
    chart = _read(ana, f"/api/maps/{created.json()['id']}")
    assert chart.status_code == 200
    cells = {Hex(item["q"], item["r"]): item["ground"] for item in chart.json()["cells"]}
    assert all(cells[rotate(cell, 3)] == ground for cell, ground in cells.items())
    assert _read(boa, f"/api/maps/{created.json()['id']}").status_code == 404

    hidden = _table(ana, boa, blind=True, map_id=created.json()["id"])
    known = [item for item in hidden["hexes"] if item["known"]]
    assert len(known) < len(hidden["hexes"])
    assert all("ground" in item for item in known)
    assert all("ground" not in item for item in hidden["hexes"] if not item["known"])
