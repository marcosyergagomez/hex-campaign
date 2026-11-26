"""Push bus delivers campaign and notification events after commits."""

import asyncio
from datetime import date

import pytest
from django.utils import timezone
from fastapi.testclient import TestClient

from apps.accounts.models import User
from apps.accounts.throttle import clear_login_limits
from apps.campaigns.live import LiveBus
from apps.campaigns.models import Notification
from apps.campaigns.records import accept_alias, create_campaign, invite_alias, play
from config.asgi import application
from hexcampaign.domain.lobby import choose_identity


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
def client():
    with TestClient(application, base_url="https://testserver") as session:
        yield session


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


def test_live_bus_delivers_to_subscriber() -> None:
    async def run() -> None:
        bus = LiveBus()
        queue = bus.subscribe(7)
        bus.publish_users([7], {"type": "notification"})
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event == {"type": "notification"}
        bus.unsubscribe(7, queue)

    asyncio.run(run())


def test_live_bus_caps_subscriptions_per_user() -> None:
    async def run() -> None:
        bus = LiveBus()
        held = [bus.subscribe(9) for _ in range(LiveBus.MAX_SUBSCRIPTIONS)]
        with pytest.raises(RuntimeError, match="too_many_streams"):
            bus.subscribe(9)
        for queue in held:
            bus.unsubscribe(9, queue)
        bus.subscribe(9)

    asyncio.run(run())


@pytest.mark.django_db(transaction=True)
def test_invite_pushes_notification_event(monkeypatch) -> None:
    seen: list[dict] = []

    def capture(user_ids, event):
        seen.append({"users": list(user_ids), "event": event})

    monkeypatch.setattr("apps.campaigns.records.live_bus.publish_users", capture)

    owner = _player("push_owner@example.com", "push_owner")
    guest = _player("push_guest@example.com", "push_guest")
    campaign, game = create_campaign(owner, "Push", RULES)
    campaign, game = invite_alias(owner, campaign.id, game.revision, guest.alias)
    before = len(seen)
    revision = game.revision
    campaign, game = invite_alias(owner, campaign.id, game.revision, guest.alias)

    assert game.revision == revision
    assert len(seen) == before
    assert Notification.objects.filter(user=guest, kind="campaign_invite").count() == 1
    assert any(
        row["event"].get("type") == "notification" and guest.pk in row["users"]
        for row in seen
    )
    assert any(
        row["event"].get("type") == "campaign" and row["event"].get("campaign_id") == str(campaign.id)
        for row in seen
    )


@pytest.mark.django_db(transaction=True)
def test_taking_a_color_pushes_the_campaign_to_the_other_seat(monkeypatch) -> None:
    seen: list[dict] = []

    def capture(user_ids, event):
        seen.append({"users": list(user_ids), "event": event})

    monkeypatch.setattr("apps.campaigns.records.live_bus.publish_users", capture)
    owner = _player("color_owner@example.com", "color_owner")
    guest = _player("color_guest@example.com", "color_guest")
    campaign, game = create_campaign(owner, "Colores", RULES)
    campaign, game = invite_alias(owner, campaign.id, game.revision, guest.alias)
    campaign, game = accept_alias(guest, campaign.id, game.revision)
    seen.clear()

    campaign, game = play(
        owner,
        campaign.id,
        game.revision,
        lambda current: choose_identity(current, str(owner.pk), "empire", "#c62828"),
    )

    pushed = [
        row["event"]
        for row in seen
        if guest.pk in row["users"]
        and owner.pk in row["users"]
        and row["event"].get("type") == "campaign"
        and row["event"].get("campaign_id") == str(campaign.id)
        and row["event"].get("revision") == game.revision
    ]
    assert pushed
    assert any(
        seat.get("player_id") == str(owner.pk) and seat.get("color") == "#c62828"
        for seat in pushed[0].get("seats", [])
    )


@pytest.mark.django_db(transaction=True)
def test_promoting_a_player_notifies_only_that_player(monkeypatch) -> None:
    from apps.campaigns.records import _sync
    from hexcampaign.domain.game import to_dict
    from hexcampaign.domain.turn import promote_player

    seen: list[dict] = []

    def capture(user_ids, event):
        seen.append({"users": list(user_ids), "event": event})

    monkeypatch.setattr("apps.campaigns.records.live_bus.publish_users", capture)
    owner = _player("promote_owner@example.com", "promote_owner")
    guest = _player("promote_guest@example.com", "promote_guest")
    campaign, game = create_campaign(owner, "Mando", RULES)
    campaign, game = invite_alias(owner, campaign.id, game.revision, guest.alias)
    campaign, game = accept_alias(guest, campaign.id, game.revision)
    game.phase = "orders"
    game.turn = 1
    campaign.state = to_dict(game)
    campaign.save(update_fields=["state", "phase"])
    _sync(campaign, game)
    seen.clear()

    campaign, game = play(
        owner,
        campaign.id,
        game.revision,
        lambda current: promote_player(current, str(owner.pk), str(guest.pk)),
    )

    notes = list(Notification.objects.filter(user=guest, kind="campaign_admin"))
    assert len(notes) == 1
    assert notes[0].payload["campaign_id"] == str(campaign.id)
    assert notes[0].payload["campaign_name"] == "Mando"
    assert notes[0].read_at is None
    assert Notification.objects.filter(user=owner, kind="campaign_admin").count() == 0
    assert any(
        row["users"] == [guest.pk] and row["event"] == {"type": "notification"}
        for row in seen
    )
    assert next(member.role for member in game.members if member.player_id == str(guest.pk)) == "admin"

    seen.clear()
    play(
        owner,
        campaign.id,
        game.revision,
        lambda current: promote_player(current, str(owner.pk), str(guest.pk)),
    )
    assert Notification.objects.filter(user=guest, kind="campaign_admin").count() == 1


@pytest.mark.django_db(transaction=True)
def test_an_opened_battle_notifies_the_players_who_can_see_it(monkeypatch) -> None:
    from django.utils import timezone

    from hexcampaign.domain.clock import stamp
    from hexcampaign.domain.game import Battle, bump

    seen: list[dict] = []

    def capture(user_ids, event):
        seen.append({"users": list(user_ids), "event": event})

    monkeypatch.setattr("apps.campaigns.records.live_bus.publish_users", capture)
    owner = _player("battle_owner@example.com", "battle_owner")
    guest = _player("battle_guest@example.com", "battle_guest")
    campaign, game = create_campaign(owner, "Choque", RULES)
    campaign, game = invite_alias(owner, campaign.id, game.revision, guest.alias)
    campaign, game = accept_alias(guest, campaign.id, game.revision)
    seen.clear()

    def open_battle(current):
        current.battles.append(
            Battle(
                id="b9",
                turn=max(current.turn, 1),
                q=0,
                r=0,
                army_ids=[],
                players=[str(owner.pk), str(guest.pk)],
                reports={},
                result=None,
                reverted=False,
                opened_at=stamp(timezone.now()),
            )
        )
        return bump(current)

    campaign, game = play(owner, campaign.id, game.revision, open_battle)

    notes = list(Notification.objects.filter(kind="campaign_battle"))
    assert {note.user_id for note in notes} == {owner.pk, guest.pk}
    assert {note.payload["battle_id"] for note in notes} == {"b9"}
    assert {note.payload["campaign_name"] for note in notes} == {"Choque"}
    assert any(row["event"] == {"type": "notification"} for row in seen)
    assert game.battles[-1].id == "b9"

    seen.clear()
    play(owner, campaign.id, game.revision, bump)
    assert Notification.objects.filter(kind="campaign_battle").count() == 2


@pytest.mark.django_db(transaction=True)
def test_events_stream_requires_session(client, settings) -> None:
    from api.player_session import CSRF_COOKIE

    settings.API_ORIGIN = ORIGIN
    denied = client.get("/api/events")
    assert denied.status_code == 401

    user = _player("stream@example.com", "stream_one")
    login = client.post(
        "/api/session",
        json={"email": user.email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert login.status_code == 200, login.text
    assert CSRF_COOKIE in client.cookies

    with client.stream("GET", "/api/events", headers={"origin": ORIGIN}) as response:
        assert response.status_code == 200, response.text
        assert "text/event-stream" in response.headers["content-type"]
        line = next(response.iter_lines())
        assert line.startswith("data: ")
        assert '"ready"' in line
