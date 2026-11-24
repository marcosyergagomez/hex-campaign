"""The campaign API hides secret orders, rejects a stale revision, and follows a closed account."""

from datetime import date

import pytest
from django.utils import timezone
from fastapi.testclient import TestClient

from api.player_session import CSRF_COOKIE
from apps.accounts.models import User
from apps.accounts.throttle import clear_login_limits
from apps.campaigns.models import Seat
from config.asgi import application
from hexcampaign.domain.hexes import Hex, neighbors

PASSWORD = "una-clave-larga"
ORIGIN = "http://testserver"
RULES = {
    "seats": 2,
    "armies": 1,
    "movement": 1,
    "map_size": 19,
    "visibility": "full",
    "victory": "armies",
    "hold_turns": 3,
    "placement": "app",
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


def _login(client, email: str):
    response = client.post(
        "/api/session",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert response.status_code == 200, response.text
    return response


def _write(client, path: str, body: dict):
    response = client.post(path, json=body, headers=_headers(client, write=True))
    return response


def _read(client, path: str):
    return client.get(path, headers=_headers(client, write=False))


def _started(ana, boa):
    created = _write(ana, "/api/campaigns", {"name": "Norte", "rules": RULES})
    assert created.status_code == 201, created.text
    campaign = created.json()
    link = _write(ana, f"/api/campaigns/{campaign['id']}/links", {})
    assert link.status_code == 201, link.text
    token = link.json()["token"]
    preview = _read(boa, f"/api/invitations/{token}")
    assert preview.status_code == 200, preview.text
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
def test_a_rival_cannot_read_the_secret_order_and_a_stale_write_does_nothing(clients) -> None:
    ana, boa = clients
    owner = _player("ana@example.com", "ana_one")
    rival = _player("boa@example.com", "boa_two")
    _login(ana, owner.email)
    _login(boa, rival.email)
    started = _started(ana, boa)
    listed = _read(boa, "/api/campaigns")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == started["id"]

    army = next(item for item in started["armies"] if item["player_id"] == str(owner.pk))
    board = {Hex(item["q"], item["r"]) for item in started["hexes"]}
    dest = next(cell for cell in neighbors(Hex(army["q"], army["r"])) if cell in board)
    locked = _write(
        ana,
        f"/api/campaigns/{started['id']}/orders",
        {"revision": started["revision"], "orders": {army["id"]: [{"q": dest.q, "r": dest.r}]}},
    )
    assert locked.status_code == 200, locked.text

    seen = _read(boa, f"/api/campaigns/{started['id']}")
    assert seen.status_code == 200, seen.text
    assert army["id"] not in seen.json()["orders"]

    stale = _write(
        boa,
        f"/api/campaigns/{started['id']}/orders",
        {"revision": started["revision"], "orders": {}},
    )
    assert stale.status_code == 409
    assert stale.json()["errors"]["revision"] == ["La campaña ha cambiado. Vuelve a leerla."]
    again = _read(ana, f"/api/campaigns/{started['id']}")
    assert again.json()["revision"] == locked.json()["revision"]
    assert again.json()["orders"][army["id"]] == [{"q": dest.q, "r": dest.r}]


@pytest.mark.django_db(transaction=True)
def test_closing_the_account_leaves_the_seat_inactive(clients) -> None:
    ana, boa = clients
    owner = _player("ana@example.com", "ana_one")
    rival = _player("boa@example.com", "boa_two")
    _login(ana, owner.email)
    _login(boa, rival.email)
    started = _started(ana, boa)

    rival.is_active = False
    rival.save(update_fields=["is_active"])

    seen = _read(ana, f"/api/campaigns/{started['id']}")
    member = next(item for item in seen.json()["members"] if item["player_id"] == str(rival.pk))
    assert member["status"] == "inactive"
    assert Seat.objects.get(campaign_id=started["id"], user=rival).status == "inactive"


@pytest.mark.django_db(transaction=True)
def test_a_campaign_post_can_carry_eight_kilobytes_but_not_more(clients) -> None:
    ana, _boa = clients
    _player("ana@example.com", "ana_one")
    _login(ana, "ana@example.com")
    allowed = _write(ana, "/api/campaigns", {"name": "Norte", "rules": RULES, "pad": "x" * 5000})
    assert allowed.status_code != 413

    rejected = ana.post(
        "/api/campaigns",
        content=b'{"name":"' + b"x" * 9000 + b'"}',
        headers={**_headers(ana, write=True), "content-type": "application/json"},
    )
    assert rejected.status_code == 413
    assert rejected.json()["errors"]["campaign"] == ["La solicitud es demasiado grande."]
