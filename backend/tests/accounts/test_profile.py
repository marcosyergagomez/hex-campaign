"""The signed-in player can read and update their profile."""

from datetime import date

import pytest
from django.utils import timezone
from fastapi.testclient import TestClient

from api.player_session import CSRF_COOKIE
from apps.accounts.models import User
from apps.campaigns.models import Seat
from config.asgi import application
from hexcampaign.domain.game import from_dict


PASSWORD = "una-clave-larga"


@pytest.fixture
def client():
    with TestClient(application, base_url="https://testserver") as http:
        yield http


def _player(
    email: str = "ada@example.com",
    *,
    alias: str = "ada_lovelace",
    sex: str = "woman",
) -> User:
    user = User.objects.create_user(
        email,
        PASSWORD,
        alias=alias,
        birth_date=date(1990, 1, 1),
        sex=sex,
    )
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user


def _login(client, email: str = "ada@example.com") -> None:
    response = client.post(
        "/api/session",
        json={"email": email, "password": PASSWORD},
        headers={"origin": "http://testserver"},
    )
    assert response.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_profile_requires_session(client) -> None:
    assert client.get("/api/profile").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_profile_returns_personal_fields(client) -> None:
    _player()
    _login(client)

    response = client.get("/api/profile")

    assert response.status_code == 200
    assert response.json() == {
        "email": "ada@example.com",
        "alias": "ada_lovelace",
        "sex": "woman",
        "birth_date": "1990-01-01",
    }
    # Session still hides sex and birth date.
    who = client.get("/api/session")
    assert who.json() == {"email": "ada@example.com", "alias": "ada_lovelace"}


@pytest.mark.django_db(transaction=True)
def test_profile_updates_alias_sex_and_password(client) -> None:
    user = _player()
    _login(client)
    csrf = client.cookies.get(CSRF_COOKIE)

    response = client.post(
        "/api/profile",
        json={
            "alias": "nueva_ada",
            "sex": "undisclosed",
            "password": "otra-clave-larga",
            "current_password": PASSWORD,
        },
        headers={"origin": "http://testserver", "x-csrf-token": csrf},
    )

    assert response.status_code == 200
    assert response.json()["alias"] == "nueva_ada"
    assert response.json()["sex"] == "undisclosed"
    user.refresh_from_db()
    assert user.alias == "nueva_ada"
    assert user.sex == "undisclosed"
    assert user.check_password("otra-clave-larga")


@pytest.mark.django_db(transaction=True)
def test_profile_rejects_wrong_current_password(client) -> None:
    _player()
    _login(client)
    csrf = client.cookies.get(CSRF_COOKIE)

    response = client.post(
        "/api/profile",
        json={
            "alias": "ada_lovelace",
            "sex": "woman",
            "password": "otra-clave-larga",
            "current_password": "clave-equivocada",
        },
        headers={"origin": "http://testserver", "x-csrf-token": csrf},
    )

    assert response.status_code == 400
    assert "current_password" in response.json()["errors"]


@pytest.mark.django_db(transaction=True)
def test_profile_mirrors_alias_into_campaign_seats(client) -> None:
    user = _player()
    from apps.campaigns.records import create_campaign

    rules = {
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
    campaign, _game = create_campaign(user, "Mesa", rules)
    _login(client)
    csrf = client.cookies.get(CSRF_COOKIE)

    response = client.post(
        "/api/profile",
        json={"alias": "ada_nueva", "sex": "woman"},
        headers={"origin": "http://testserver", "x-csrf-token": csrf},
    )

    assert response.status_code == 200
    seat = Seat.objects.get(campaign=campaign, user=user)
    assert seat.alias == "ada_nueva"
    campaign.refresh_from_db()
    member = next(m for m in from_dict(campaign.state).members if m.player_id == str(user.pk))
    assert member.alias == "ada_nueva"
