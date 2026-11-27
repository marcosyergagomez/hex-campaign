"""The campaign API hides secret orders, rejects a stale revision, and follows a closed account."""

from datetime import date

import pytest
from django.utils import timezone
from fastapi.testclient import TestClient

from api.player_session import CSRF_COOKIE
from apps.accounts.models import User
from apps.accounts.throttle import clear_login_limits
from apps.campaigns.models import Seat
from apps.campaigns.records import CampaignError, create_campaign, list_campaigns
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
    sealed = _read(ana, f"/api/campaigns/{campaign['id']}")
    assert sealed.status_code == 200, sealed.text
    assert sealed.json()["hexes"] == []
    assert sealed.json()["phase"] == "recruiting"
    started = _write(
        ana,
        f"/api/campaigns/{campaign['id']}/start",
        {"revision": chosen.json()["revision"], "admins": []},
    )
    assert started.status_code == 200, started.text
    assert len(started.json()["hexes"]) > 0
    return started.json()


@pytest.mark.django_db(transaction=True)
def test_identity_choices_are_private_writes_validated_and_persisted(clients) -> None:
    ana, boa = clients
    owner = _player("ana-banner@example.com", "ana_one")
    rival = _player("boa-banner@example.com", "boa_two")
    assert _read(ana, "/api/campaign-identity").status_code == 401
    _login(ana, owner.email)
    _login(boa, rival.email)
    options = _read(ana, "/api/campaign-identity")
    assert options.status_code == 200
    assert any(item == {"id": "cathay", "legacy": False} for item in options.json()["factions"])
    assert any(item == {"id": "skaven", "legacy": True} for item in options.json()["factions"])
    created = _write(ana, "/api/campaigns", {"name": "Estandartes", "rules": RULES}).json()
    path = f"/api/campaigns/{created['id']}"
    identity = {"revision": created["revision"], "faction": "cathay", "color": "#c62828"}
    assert _write(boa, f"{path}/identity", identity).status_code == 403
    rejected = _write(ana, f"{path}/identity", {**identity, "color": "url(https://example.com)"})
    assert rejected.status_code == 422
    assert _read(ana, path).json()["revision"] == created["revision"]
    saved = _write(ana, f"{path}/identity", identity)
    assert saved.status_code == 200, saved.text
    read = _read(ana, path).json()
    assert read["you"]["faction"] == "cathay"
    assert read["members"][0]["color"] == "#c62828"
    assert _write(ana, f"{path}/identity", identity).status_code == 409
    link = _write(ana, f"{path}/links", {}).json()["token"]
    joined = _write(boa, f"/api/invitations/{link}/accept", {"revision": read["revision"]}).json()
    missing = _write(ana, f"{path}/start", {"revision": joined["revision"]})
    assert missing.status_code == 422
    assert missing.json()["errors"]["campaign"] == [
        "Todos los jugadores deben elegir raza y color antes de empezar.",
    ]
    assert _read(ana, path).json()["hexes"] == []
    duplicate = _write(boa, f"{path}/identity", {**identity, "revision": joined["revision"]})
    assert duplicate.status_code == 422
    assert duplicate.json()["errors"]["campaign"] == ["Ese color ya pertenece a otro jugador."]
    held = _write(boa, f"{path}/color", {"revision": joined["revision"], "color": "#ef6c00"})
    assert held.status_code == 200, held.text
    visible = _read(ana, path)
    assert visible.status_code == 200, visible.text
    body = visible.json()
    boa_color = next(member["color"] for member in body["members"] if member["alias"] == "boa_two")
    assert boa_color == "#ef6c00"
    blocked = _write(ana, f"{path}/color", {"revision": body["revision"], "color": "#ef6c00"})
    assert blocked.status_code == 422
    assert blocked.json()["errors"]["campaign"] == ["Ese color ya pertenece a otro jugador."]


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

    own = [
        item for item in started["armies"]
        if item.get("player_id") == str(owner.pk) and item.get("q") is not None
    ]
    army = next(item for item in own if item["kind"] == "army")
    board = {Hex(item["q"], item["r"]) for item in started["hexes"]}
    forts = {(item["q"], item["r"]) for item in started["fortresses"]}
    known = {
        (item["q"], item["r"]): item for item in started["hexes"] if item.get("known")
    }

    def _passable(cell: Hex) -> bool:
        item = known.get((cell.q, cell.r))
        if item is None or (cell.q, cell.r) in forts:
            return False
        return item.get("ground") not in {"lago", "acantilado", "montana_rocosa"}

    dest = next(
        cell for cell in neighbors(Hex(army["q"], army["r"])) if cell in board and _passable(cell)
    )
    orders = {item["id"]: [] for item in own}
    orders[army["id"]] = [{"q": dest.q, "r": dest.r}]
    locked = _write(
        ana,
        f"/api/campaigns/{started['id']}/orders",
        {"revision": started["revision"], "orders": orders},
    )
    assert locked.status_code == 200, locked.text

    seen = _read(boa, f"/api/campaigns/{started['id']}")
    assert seen.status_code == 200, seen.text
    assert army["id"] not in seen.json()["orders"]
    assert seen.json()["playback"]["moves"] == []
    ana_seat = next(member for member in seen.json()["members"] if member["alias"] == "ana_one")
    assert ana_seat["orders_locked"] is True

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

    boa_now = _read(boa, f"/api/campaigns/{started['id']}")
    stay = {
        item["id"]: []
        for item in boa_now.json()["armies"]
        if item.get("player_id") == str(rival.pk)
    }
    resolved = _write(
        boa,
        f"/api/campaigns/{started['id']}/orders",
        {"revision": boa_now.json()["revision"], "orders": stay},
    )
    assert resolved.status_code == 200, resolved.text
    film = resolved.json()["playback"]
    assert film["turn"] >= 1
    assert all("order" not in move for move in film["moves"])
    marched = [move for move in film["moves"] if move["army_id"] == army["id"]]
    if marched:
        assert marched[0]["from"] != marched[0]["steps"][-1]


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
def test_a_campaign_post_can_carry_a_lore_blurb_but_not_an_oversized_body(clients) -> None:
    ana, _boa = clients
    _player("ana@example.com", "ana_one")
    _login(ana, "ana@example.com")
    allowed = _write(
        ana,
        "/api/campaigns",
        {"name": "Norte", "rules": RULES, "description": "x" * 15000},
    )
    assert allowed.status_code != 413
    assert allowed.status_code == 201, allowed.text
    assert len(allowed.json()["description"]) == 15000

    rejected = ana.post(
        "/api/campaigns",
        content=b'{"name":"' + b"x" * 70000 + b'"}',
        headers={**_headers(ana, write=True), "content-type": "application/json"},
    )
    assert rejected.status_code == 413
    assert rejected.json()["errors"]["campaign"] == ["La solicitud es demasiado grande."]


@pytest.mark.django_db(transaction=True)
def test_a_stranger_cannot_probe_a_campaign_by_id(clients) -> None:
    ana, boa = clients
    owner = _player("owner-private@example.com", "duena")
    stranger = _player("stranger@example.com", "ajena")
    _login(ana, owner.email)
    _login(boa, stranger.email)
    created = _write(ana, "/api/campaigns", {"name": "Privada", "rules": RULES})
    assert created.status_code == 201, created.text
    probed = _read(boa, f"/api/campaigns/{created.json()['id']}")
    assert probed.status_code == 404
    assert probed.json()["errors"]["campaign"] == [
        "No hay ninguna campaña con ese identificador.",
    ]


@pytest.mark.django_db(transaction=True)
def test_a_player_may_prepare_many_but_only_three_running() -> None:
    from apps.campaigns.models import Campaign
    from apps.campaigns.records import play
    from hexcampaign.domain.game import bump

    owner = _player("tope@example.com", "tope_one")
    prepared = []
    for name in ("Uno", "Dos", "Tres", "Cuatro"):
        campaign, game = create_campaign(owner, name, RULES)
        prepared.append((campaign, game))
    assert Campaign.objects.filter(created_by=owner).count() == 4

    Campaign.objects.filter(created_by=owner).exclude(name="Cuatro").update(phase="orders")
    fourth, game = prepared[3]

    def enter_orders(current):
        current.phase = "orders"
        current.turn = 1
        return bump(current)

    with pytest.raises(CampaignError) as refused:
        play(owner, fourth.id, game.revision, enter_orders)
    assert refused.value.code == "campaign_limit"

    Campaign.objects.filter(created_by=owner, name="Uno").update(phase="finished")
    campaign, updated = play(owner, fourth.id, game.revision, enter_orders)
    assert updated.phase == "orders"
    assert campaign.phase == "orders"


@pytest.mark.django_db(transaction=True)
def test_an_inactive_account_cannot_open_a_campaign() -> None:
    user = _player("cerrada@example.com", "cerrada")
    User.objects.filter(pk=user.pk).update(is_active=False)

    with pytest.raises(CampaignError) as caught:
        create_campaign(user, "Norte", RULES)

    assert caught.value.code == "account_inactive"


@pytest.mark.django_db(transaction=True)
def test_owner_can_delete_a_prepared_campaign(clients, settings) -> None:
    from apps.campaigns.models import Campaign

    settings.API_ORIGIN = ORIGIN
    ana, _boa = clients
    _player("borrar@example.com", "borrar_mesa")
    _login(ana, "borrar@example.com")
    created = _write(ana, "/api/campaigns", {"name": "Borrable", "rules": RULES})
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]

    refused = _write(ana, f"/api/campaigns/{campaign_id}/scrap", {"confirm_name": "Otro"})
    assert refused.status_code == 422, refused.text
    assert refused.json()["errors"]["campaign"] == [
        "Escribe el nombre exacto de la campaña para confirmar.",
    ]

    deleted = _write(ana, f"/api/campaigns/{campaign_id}/scrap", {"confirm_name": "Borrable"})
    assert deleted.status_code == 204, deleted.text
    assert not Campaign.objects.filter(pk=campaign_id).exists()


@pytest.mark.django_db(transaction=True)
def test_owner_leaving_a_running_campaign_hands_over_and_hides_it() -> None:
    from apps.campaigns.records import _sync, scrap_campaign
    from hexcampaign.domain.game import find_member, from_dict, to_dict
    from hexcampaign.domain.lobby import accept_seat, invite_player

    owner = _player("correr@example.com", "correr")
    guest = _player("releve@example.com", "releve")
    third = _player("tercera@example.com", "tercera")
    wide = {**RULES, "seats": 3}
    campaign, game = create_campaign(owner, "Marcha", wide)
    game = invite_player(game, str(owner.pk), str(guest.pk), guest.alias)
    game = accept_seat(game, str(guest.pk), guest.alias)
    game = invite_player(game, str(owner.pk), str(third.pk), third.alias)
    game = accept_seat(game, str(third.pk), third.alias)
    game.phase = "orders"
    game.turn = 1
    campaign.state = to_dict(game)
    campaign.phase = "orders"
    campaign.save(update_fields=["state", "phase"])
    _sync(campaign, game)

    scrap_campaign(owner, campaign.id, "Marcha")
    campaign.refresh_from_db()
    updated = from_dict(campaign.state)
    left = find_member(updated, str(owner.pk))
    assert left is not None and left.status == "expelled"
    assert find_member(updated, str(guest.pk)).role == "owner" or find_member(
        updated, str(third.pk)
    ).role == "owner"
    assert updated.phase == "orders"
    assert list_campaigns(owner) == []
    assert any(row["id"] == str(campaign.id) for row in list_campaigns(guest))
    assert any(row["id"] == str(campaign.id) for row in list_campaigns(third))


@pytest.mark.django_db(transaction=True)
def test_player_leaving_becomes_inactive_and_can_be_restored() -> None:
    from apps.campaigns.models import Seat
    from apps.campaigns.records import play, scrap_campaign
    from hexcampaign.domain.game import find_member, from_dict, to_dict
    from hexcampaign.domain.lobby import accept_seat, invite_player
    from hexcampaign.domain.turn import restore_player

    owner = _player("mesa@example.com", "mesa_due")
    guest = _player("sale@example.com", "sale_uno")
    campaign, game = create_campaign(owner, "Retirada", RULES)
    game = invite_player(game, str(owner.pk), str(guest.pk), guest.alias)
    game = accept_seat(game, str(guest.pk), guest.alias)
    game.phase = "orders"
    game.turn = 1
    campaign.state = to_dict(game)
    campaign.phase = "orders"
    campaign.save(update_fields=["state", "phase"])
    from apps.campaigns.records import _sync

    _sync(campaign, game)

    scrap_campaign(guest, campaign.id, "Retirada")
    campaign.refresh_from_db()
    updated = from_dict(campaign.state)
    seat = find_member(updated, str(guest.pk))
    assert seat is not None
    assert seat.status == "inactive"
    assert Seat.objects.get(campaign=campaign, user=guest).status == "inactive"
    assert list_campaigns(guest) == []

    campaign, restored = play(
        owner,
        campaign.id,
        updated.revision,
        lambda current: restore_player(current, str(owner.pk), str(guest.pk)),
    )
    assert find_member(restored, str(guest.pk)).status == "active"
    assert any(row["id"] == str(campaign.id) for row in list_campaigns(guest))


@pytest.mark.django_db(transaction=True)
def test_the_list_reads_the_phase_column() -> None:
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    user = _player("lista@example.com", "lista")
    campaign, _game = create_campaign(user, "Norte", RULES)

    with CaptureQueriesContext(connection) as captured:
        rows = list_campaigns(user)

    assert rows == [
        {
            "id": str(campaign.id),
            "name": "Norte",
            "role": "owner",
            "status": "active",
            "phase": "recruiting",
        }
    ]
    sql = " ".join(query["sql"] for query in captured.captured_queries)
    assert "state" not in sql


@pytest.mark.django_db(transaction=True)
def test_campaign_pulse_tracks_revision_after_ready(clients, settings) -> None:
    settings.API_ORIGIN = ORIGIN
    ana, boa = clients
    _player("pulso_a@example.com", "pulso_a")
    _player("pulso_b@example.com", "pulso_b")
    _login(ana, "pulso_a@example.com")
    _login(boa, "pulso_b@example.com")

    created = _write(ana, "/api/campaigns", {"name": "Pulso", "rules": RULES}).json()
    campaign_id = created["id"]
    link = _write(ana, f"/api/campaigns/{campaign_id}/links", {}).json()["token"]
    preview = _read(boa, f"/api/invitations/{link}").json()
    joined = _write(
        boa,
        f"/api/invitations/{link}/accept",
        {"revision": preview["revision"]},
    ).json()

    pulse = _read(ana, f"/api/campaigns/{campaign_id}/pulse")
    assert pulse.status_code == 200, pulse.text
    assert pulse.json() == {"revision": joined["revision"], "phase": "recruiting"}

    revision = joined["revision"]
    for client, faction, color in (
        (ana, "empire", "#c62828"),
        (boa, "skaven", "#1565c0"),
    ):
        identity = _write(
            client,
            f"/api/campaigns/{campaign_id}/identity",
            {"revision": revision, "faction": faction, "color": color},
        )
        assert identity.status_code == 200, identity.text
        revision = identity.json()["revision"]
        ready = _write(client, f"/api/campaigns/{campaign_id}/ready", {"revision": revision})
        assert ready.status_code == 200, ready.text
        revision = ready.json()["revision"]

    later = _read(ana, f"/api/campaigns/{campaign_id}/pulse")
    assert later.status_code == 200, later.text
    assert later.json() == {"revision": revision, "phase": "recruiting"}
    assert later.json()["revision"] > pulse.json()["revision"]


@pytest.mark.django_db(transaction=True)
def test_admin_invite_creates_notification_and_guest_can_join(clients, settings) -> None:
    from apps.campaigns.models import Notification

    settings.API_ORIGIN = ORIGIN
    ana, boa = clients
    owner = _player("invita@example.com", "anfitrion")
    guest = _player("invitado@example.com", "convidado")
    _login(ana, owner.email)
    _login(boa, guest.email)

    created = _write(ana, "/api/campaigns", {"name": "Mesa", "rules": RULES})
    assert created.status_code == 201, created.text
    campaign = created.json()

    found = _read(ana, "/api/players?q=con")
    assert found.status_code == 200, found.text
    assert found.json() == [{"alias": "convidado"}]

    invited = _write(
        ana,
        f"/api/campaigns/{campaign['id']}/invitations",
        {"revision": campaign["revision"], "alias": "convidado"},
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["revision"] == campaign["revision"] + 1
    assert Notification.objects.filter(user=guest, kind="campaign_invite").count() == 1

    notes = _read(boa, "/api/notifications")
    assert notes.status_code == 200, notes.text
    rows = notes.json()
    assert len(rows) == 1
    assert rows[0]["kind"] == "campaign_invite"
    assert rows[0]["read"] is False
    assert rows[0]["payload"]["campaign_id"] == campaign["id"]
    assert rows[0]["payload"]["campaign_name"] == "Mesa"
    assert isinstance(rows[0]["payload"]["revision"], int)

    joined = _write(
        boa,
        f"/api/campaigns/{campaign['id']}/join",
        {"revision": rows[0]["payload"]["revision"]},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["you"]["alias"] == "convidado"
    assert Notification.objects.filter(user=guest, read_at__isnull=False).count() == 1


@pytest.mark.django_db(transaction=True)
def test_revoked_and_declined_invites_cannot_join(clients) -> None:
    ana, boa = clients
    owner = _player("veto_owner@example.com", "veto_owner")
    guest = _player("veto_guest@example.com", "veto_guest")
    _login(ana, owner.email)
    _login(boa, guest.email)
    created = _write(ana, "/api/campaigns", {"name": "Veto", "rules": RULES})
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]
    invited = _write(
        ana,
        f"/api/campaigns/{campaign_id}/invitations",
        {"revision": created.json()["revision"], "alias": guest.alias},
    )
    assert invited.status_code == 200, invited.text
    listed = _read(ana, f"/api/campaigns/{campaign_id}/invitations")
    assert listed.status_code == 200, listed.text
    invitation_id = listed.json()[0]["id"]
    revoked = _write(ana, f"/api/campaigns/{campaign_id}/invitations/{invitation_id}/revoke", {})
    assert revoked.status_code == 204, revoked.text
    blocked = _write(
        boa,
        f"/api/campaigns/{campaign_id}/join",
        {"revision": invited.json()["revision"]},
    )
    assert blocked.status_code == 404

    resent = _write(ana, f"/api/campaigns/{campaign_id}/invitations/{invitation_id}/resend", {})
    assert resent.status_code == 204, resent.text
    fresh = _read(boa, "/api/invitations")
    assert fresh.status_code == 200, fresh.text
    revision = fresh.json()[0]["revision"]
    declined = _write(boa, f"/api/campaigns/{campaign_id}/invitations/decline", {})
    assert declined.status_code == 204, declined.text
    again = _write(boa, f"/api/campaigns/{campaign_id}/join", {"revision": revision})
    assert again.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_cannot_invite_player_already_in_three_running() -> None:
    from apps.campaigns.models import Campaign
    from apps.campaigns.records import invite_alias

    owner = _player("dueno_limite@example.com", "dueno_lim")
    guest = _player("lleno@example.com", "lleno_tres")
    lobby, game = create_campaign(owner, "Lobby", {**RULES, "seats": 3})

    for name in ("Uno", "Dos", "Tres"):
        campaign, _doc = create_campaign(guest, name, RULES)
        Campaign.objects.filter(pk=campaign.pk).update(phase="orders")

    with pytest.raises(CampaignError) as refused:
        invite_alias(owner, lobby.id, game.revision, guest.alias)
    assert refused.value.code == "invitee_campaign_limit"
