"""A saved map is copied into the campaign. Looking at it is a choice."""

import json
from datetime import date

import pytest
from django.utils import timezone
from fastapi.testclient import TestClient

from api.player_session import CSRF_COOKIE
from apps.accounts.models import User
from apps.accounts.throttle import clear_login_limits
from config.asgi import application
from hexcampaign.domain.hexes import disk

PASSWORD = "una-clave-larga"
ORIGIN = "http://testserver"
RULES = {
    "seats": 2,
    "armies": 1,
    "movement": 1,
    "map_size": 271,
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


def _delete(client, path: str):
    return client.delete(path, headers=_headers(client, write=True))


def _read(client, path: str):
    return client.get(path, headers=_headers(client, write=False))


def _preparing(ana, boa, *, blind: bool, map_id: str, size: int = 271) -> dict:
    created = _write(
        ana,
        "/api/campaigns",
        {
            "name": "Norte",
            "rules": {**RULES, "map_size": size, "placement": "app"},
            "map_id": map_id,
            "blind": blind,
        },
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
    chosen = joined
    for client, faction, color in ((ana, "empire", "#c62828"), (boa, "skaven", "#1565c0")):
        chosen = _write(client, f"/api/campaigns/{campaign['id']}/identity", {
            "revision": chosen.json()["revision"], "faction": faction, "color": color,
        })
        assert chosen.status_code == 200, chosen.text
        chosen = _write(
            client,
            f"/api/campaigns/{campaign['id']}/ready",
            {"revision": chosen.json()["revision"]},
        )
        assert chosen.status_code == 200, chosen.text
    started = _write(
        ana,
        f"/api/campaigns/{campaign['id']}/start",
        {"revision": chosen.json()["revision"], "admins": []},
    )
    assert started.status_code == 200, started.text
    view = started.json()
    assert view["phase"] == "preparing"
    return view


def _table(ana, boa, *, blind: bool, map_id: str, size: int = 271) -> dict:
    view = _preparing(ana, boa, blind=blind, map_id=map_id, size=size)
    campaign_id = view["id"]
    for client in (ana, boa):
        view = _write(
            client,
            f"/api/campaigns/{campaign_id}/roads/ready",
            {"revision": view["revision"]},
        ).json()
    assert view["phase"] == "orders"
    return _read(ana, f"/api/campaigns/{campaign_id}").json()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(("size", "home"), [(271, 19), (397, 28), (547, 38)])
def test_a_generated_map_stays_hidden_when_the_owner_does_not_look(clients, size, home) -> None:
    ana, boa = clients
    owner = _player("ana-map@example.com", "AnaMapa")
    _player("boa-map@example.com", "BoaMapa")
    _login(ana, owner.email)
    _login(boa, "boa-map@example.com")
    created = _write(ana, "/api/maps", {"name": "Disco", "size": size, "seats": 2})
    assert created.status_code == 201, created.text
    chart = _read(ana, f"/api/maps/{created.json()['id']}")
    assert chart.status_code == 200
    assert chart.json()["home_size"] == home
    grounds = {item["ground"] for item in chart.json()["cells"]}
    assert {"rio", "lago", "bosque", "montana"} <= grounds
    assert all(not item["road"] for item in chart.json()["cells"])
    assert _read(boa, f"/api/maps/{created.json()['id']}").status_code == 404

    hidden = _table(ana, boa, blind=True, map_id=created.json()["id"], size=size)
    known = [item for item in hidden["hexes"] if item["known"]]
    assert len(known) == home
    assert len(hidden["hexes"]) == size
    assert all("ground" in item for item in known)
    assert all("ground" not in item for item in hidden["hexes"] if not item["known"])
    assert all(not item["road"] for item in known)
    assert all("road" not in item for item in hidden["hexes"] if not item["known"])
    assert all(item["owner_id"] == str(owner.pk) for item in known)
    assert all("owner_id" not in item for item in hidden["hexes"] if not item["known"])


@pytest.mark.django_db(transaction=True)
def test_road_mutations_return_a_delta_until_preparation_ends(clients) -> None:
    from hexcampaign.domain.hexes import Hex, neighbors
    from hexcampaign.domain.terrain import IMPASSABLE

    ana, boa = clients
    owner = _player("ana-roads@example.com", "AnaCaminos")
    _player("boa-roads@example.com", "BoaCaminos")
    _login(ana, owner.email)
    _login(boa, "boa-roads@example.com")
    created = _write(ana, "/api/maps", {"name": "Caminos", "size": 271, "seats": 2})
    assert created.status_code == 201, created.text
    view = _preparing(ana, boa, blind=False, map_id=created.json()["id"])
    full_size = len(json.dumps(view, sort_keys=True))
    fort = next(item for item in view["fortresses"] if item["player_id"] == str(owner.pk))
    near = {(cell.q, cell.r) for cell in neighbors(Hex(fort["q"], fort["r"]))}
    spot = next(
        cell for cell in view["hexes"]
        if (cell["q"], cell["r"]) in near
        and cell.get("known")
        and cell.get("ground") not in IMPASSABLE
        and not cell.get("road")
    )

    placed = _write(
        ana,
        f"/api/campaigns/{view['id']}/roads",
        {"revision": view["revision"], "q": spot["q"], "r": spot["r"]},
    )
    assert placed.status_code == 200, placed.text
    delta = placed.json()
    assert delta["kind"] == "roads_delta"
    assert delta["phase"] == "preparing"
    assert delta["id"] == view["id"]
    assert len(delta["hexes"]) == 1
    assert delta["hexes"][0]["q"] == spot["q"]
    assert delta["hexes"][0]["r"] == spot["r"]
    assert delta["hexes"][0]["road"] is True
    assert delta["roads"]["laid"] == 1
    assert "members" not in delta
    assert len(json.dumps(delta, sort_keys=True)) < full_size // 5

    cleared = _write(
        ana,
        f"/api/campaigns/{view['id']}/roads/clear",
        {"revision": delta["revision"], "q": spot["q"], "r": spot["r"]},
    )
    assert cleared.status_code == 200, cleared.text
    cleared_body = cleared.json()
    assert cleared_body["kind"] == "roads_delta"
    assert cleared_body["hexes"][0]["road"] is False
    assert cleared_body["roads"]["laid"] == 0

    ready = _write(
        ana,
        f"/api/campaigns/{view['id']}/roads/ready",
        {"revision": cleared_body["revision"]},
    )
    assert ready.status_code == 200, ready.text
    waiting = ready.json()
    assert waiting["kind"] == "roads_delta"
    assert waiting["phase"] == "preparing"
    assert waiting["roads"]["ready"] is True
    assert waiting["hexes"] == []

    done = _write(
        boa,
        f"/api/campaigns/{view['id']}/roads/ready",
        {"revision": waiting["revision"]},
    )
    assert done.status_code == 200, done.text
    opened = done.json()
    assert opened.get("kind") != "roads_delta"
    assert opened["phase"] == "orders"
    assert opened["turn"] == 1
    assert "members" in opened
    assert len(opened["hexes"]) == 271


@pytest.mark.django_db(transaction=True)
def test_the_owner_can_delete_a_saved_map_and_a_rival_cannot(clients) -> None:
    ana, boa = clients
    owner = _player("ana-drop@example.com", "AnaBorra")
    _player("boa-drop@example.com", "BoaBorra")
    _login(ana, owner.email)
    _login(boa, "boa-drop@example.com")
    created = _write(ana, "/api/maps", {"name": "Viejo", "size": 271, "seats": 2})
    assert created.status_code == 201, created.text
    map_id = created.json()["id"]
    assert _delete(boa, f"/api/maps/{map_id}").status_code == 404
    assert _read(ana, f"/api/maps/{map_id}").status_code == 200
    gone = _delete(ana, f"/api/maps/{map_id}")
    assert gone.status_code == 204, gone.text
    assert _read(ana, f"/api/maps/{map_id}").status_code == 404
    assert _delete(ana, f"/api/maps/{map_id}").status_code == 404
    listed = _read(ana, "/api/maps")
    assert listed.status_code == 200
    assert all(item["id"] != map_id for item in listed.json())


@pytest.mark.django_db(transaction=True)
def test_new_scale_configuration_is_published_and_generated(clients, monkeypatch) -> None:
    monkeypatch.setattr("hexcampaign.domain.maps.TABLE_RADII", (10, 12, 14))
    ana, _ = clients
    owner = _player("ana-scales@example.com", "AnaEscalas")
    _login(ana, owner.email)
    response = _read(ana, "/api/map-scales")
    assert response.status_code == 200
    scales = response.json()
    assert [scale["size"] for scale in scales] == [331, 469, 631]
    assert [scale["home_size"] for scale in scales] == [23, 33, 44]
    for scale in scales:
        assert scale["recommend"] in scale["seats"]
    created = _write(ana, "/api/maps", {"name": "Nueva escala", "size": 331, "seats": 3})
    assert created.status_code == 201, created.text
    chart = _read(ana, f"/api/maps/{created.json()['id']}")
    assert chart.status_code == 200
    assert len(chart.json()["cells"]) == 331
    assert len(chart.json()["anchors"]) == 3
    assert chart.json()["home_size"] == 23


@pytest.mark.django_db(transaction=True)
def test_a_player_can_save_and_update_an_irregular_drawn_map(clients) -> None:
    from hexcampaign.domain.hexes import disk

    ana, _ = clients
    owner = _player("ana-draw@example.com", "AnaDibuja")
    _login(ana, owner.email)
    board = list(disk(271))[:30]
    cells = [
        {"q": cell.q, "r": cell.r, "ground": "bosque", "road": False, "bridge": False}
        for cell in board
    ]
    cells[0]["ground"] = "llanura"
    cells[1]["ground"] = "llanura"
    created = _write(
        ana,
        "/api/maps",
        {
            "name": "Costa rota",
            "size": 271,
            "cells": cells,
            "anchors": [
                {"q": board[0].q, "r": board[0].r},
                {"q": board[1].q, "r": board[1].r},
            ],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["seats"] == 2
    assert created.json()["generated"] is False
    map_id = created.json()["id"]
    chart = _read(ana, f"/api/maps/{map_id}")
    assert chart.status_code == 200
    assert len(chart.json()["cells"]) == 30

    cells[2]["ground"] = "rio"
    updated = ana.put(
        f"/api/maps/{map_id}",
        json={
            "name": "Costa rota",
            "size": 271,
            "cells": cells,
            "anchors": [
                {"q": board[0].q, "r": board[0].r},
                {"q": board[1].q, "r": board[1].r},
            ],
        },
        headers=_headers(ana, write=True),
    )
    assert updated.status_code == 200, updated.text
    assert _read(ana, f"/api/maps/{map_id}").json()["cells"][2]["ground"] == "rio"

    generated = _write(ana, "/api/maps", {"name": "Semilla", "size": 271, "seats": 2})
    assert generated.status_code == 201, generated.text
    clone = _write(ana, f"/api/maps/{generated.json()['id']}/copy", {"name": "Semilla editable"})
    assert clone.status_code == 201, clone.text
    assert clone.json()["generated"] is False
    blocked = ana.put(
        f"/api/maps/{generated.json()['id']}",
        json={"name": "X", "size": 271, "cells": cells, "anchors": []},
        headers=_headers(ana, write=True),
    )
    assert blocked.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_the_largest_drawn_map_fits_the_request_limit_and_is_saved(clients) -> None:
    ana, _ = clients
    owner = _player("ana-large@example.com", "AnaGrande")
    _login(ana, owner.email)
    body = {
        "name": "Bosque grande",
        "size": 817,
        "cells": [
            {"q": cell.q, "r": cell.r, "ground": "bosque_profundo", "road": False, "bridge": False}
            for cell in disk(817)
        ],
    }
    content = json.dumps(body).encode()
    assert len(content) > 65536
    created = ana.post(
        "/api/maps", content=content,
        headers={**_headers(ana, write=True), "content-type": "application/json"},
    )
    assert created.status_code == 201, created.text
    chart = _read(ana, f"/api/maps/{created.json()['id']}")
    assert chart.status_code == 200
    assert len(chart.json()["cells"]) == 817
