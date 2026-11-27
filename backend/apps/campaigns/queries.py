"""Reads that must not open the campaign document.

The board is `read_campaign`. Everything a player lists — their table, the
invite tray, the pulse — uses seat rows and the columns copied in
`projection.index_from_state`.
"""

from __future__ import annotations

from .errors import CampaignError
from .models import Campaign, Invitation, Seat


def list_campaigns(user) -> list[dict[str, object]]:
    # Inactive / expelled seats stay off the player's board until staff restores them.
    seats = (
        Seat.objects.filter(user=user, status__in=["active", "eliminated"])
        .select_related("campaign")
        .only("role", "status", "campaign__name", "campaign__phase")
    )
    return [
        {
            "id": str(seat.campaign_id),
            "name": seat.campaign.name,
            "role": seat.role,
            "status": seat.status,
            "phase": seat.campaign.phase,
        }
        for seat in seats
    ]


def inbox(user) -> list[dict[str, object]]:
    pending = (
        Invitation.objects.filter(
            invited_user=user,
            accepted_at__isnull=True,
            declined_at__isnull=True,
            revoked_at__isnull=True,
        )
        .select_related("campaign")
        .only("campaign__name", "campaign__revision")
    )
    return [
        {
            "id": str(item.campaign_id),
            "name": item.campaign.name,
            "revision": item.campaign.revision,
        }
        for item in pending
    ]


def campaign_pulse(user, campaign_id) -> dict[str, object]:
    """Cheap revision check so clients can refresh when another player acts."""
    row = (
        Seat.objects.filter(
            campaign_id=campaign_id,
            user=user,
            status__in=["active", "eliminated"],
        )
        .values_list("campaign__revision", "campaign__phase")
        .first()
    )
    if row is None:
        raise CampaignError("not_found")
    revision, phase = row
    if not isinstance(revision, int) or revision < 1:
        raise CampaignError("not_found")
    return {"revision": revision, "phase": phase}


def card(campaign: Campaign, *, joined: bool = False) -> dict[str, object]:
    """Invitation preview. Same shape as before, taken from the listing columns."""
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "phase": campaign.phase,
        "seats": campaign.seat_limit,
        "occupied": campaign.occupied,
        "revision": campaign.revision,
        "joined": joined,
    }
