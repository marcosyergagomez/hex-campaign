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
from apps.campaigns.records import create_campaign, invite_alias
from config.asgi import application


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


@pytest.mark.django_db(transaction=True)
def test_invite_pushes_notification_event(monkeypatch) -> None:
    seen: list[dict] = []

    def capture(user_ids, event):
        seen.append({"users": list(user_ids), "event": event})

    monkeypatch.setattr("apps.campaigns.records.live_bus.publish_users", capture)

    owner = _player("push_owner@example.com", "push_owner")
    guest = _player("push_guest@example.com", "push_guest")
    campaign, game = create_campaign(owner, "Push", RULES)
    invite_alias(owner, campaign.id, game.revision, guest.alias)

    assert Notification.objects.filter(user=guest, kind="campaign_invite").exists()
    assert any(
        row["event"].get("type") == "notification" and guest.pk in row["users"]
        for row in seen
    )
    assert any(
        row["event"].get("type") == "campaign" and row["event"].get("campaign_id") == str(campaign.id)
        for row in seen
    )


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
