"""Lists and invite previews read columns, not the campaign document."""

from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.campaigns.invitations import invite_alias, invite_link, list_invitations, preview_link
from apps.campaigns.projection import index_from_state
from apps.campaigns.queries import inbox, list_campaigns
from apps.campaigns.records import create_campaign

PASSWORD = "una-clave-larga"
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


def test_index_counts_only_seated_members() -> None:
    found = index_from_state(
        {
            "phase": "orders",
            "revision": 4,
            "turn": 2,
            "rules": {"seats": 4},
            "members": [
                {"player_id": "1", "status": "active"},
                {"player_id": "2", "status": "expelled"},
                {"player_id": "3", "status": "inactive"},
            ],
        }
    )
    assert found == {
        "phase": "orders",
        "revision": 4,
        "turn": 2,
        "seat_limit": 4,
        "occupied": 2,
    }


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


@pytest.mark.django_db
def test_lists_and_preview_do_not_read_the_document() -> None:
    owner = _player("lista@example.com", "lista_one")
    guest = _player("bandeja@example.com", "bandeja")
    campaign, game = create_campaign(owner, "Mesa", RULES)
    campaign.refresh_from_db()
    assert campaign.seat_limit == RULES["seats"]
    assert campaign.occupied == 1
    assert campaign.turn == game.turn
    assert campaign.phase == "recruiting"

    token = invite_link(owner, campaign.id)
    invite_alias(owner, campaign.id, game.revision, guest.alias)
    campaign.refresh_from_db()

    with CaptureQueriesContext(connection) as captured:
        board = list_campaigns(owner)
        pending = inbox(guest)
        listed = list_invitations(owner, campaign.id)
        shown = preview_link(guest, token)

    assert board and pending and listed
    assert pending[0]["revision"] == campaign.revision
    assert shown["seats"] == campaign.seat_limit
    assert shown["occupied"] == campaign.occupied
    assert shown["revision"] == campaign.revision
    sql = "\n".join(query["sql"] for query in captured.captured_queries)
    assert '"state"' not in sql
