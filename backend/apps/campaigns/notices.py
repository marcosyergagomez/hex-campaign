"""In-app notices. Invite rows and the campaign document stay elsewhere."""

from __future__ import annotations

from django.utils import timezone

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.view import project

from .access import _push_after_commit
from .errors import CampaignError
from .models import Campaign, Notification


def _as_int(value: object) -> int:
    if isinstance(value, str):
        return int(value)
    if isinstance(value, int):
        return value
    raise TypeError


def list_notifications(user) -> list[dict[str, object]]:
    rows = list(Notification.objects.filter(user=user).order_by("-created_at")[:40])
    wanted: list[str] = []
    for row in rows:
        if row.kind != Notification.KIND_CAMPAIGN_INVITE:
            continue
        payload = row.payload if isinstance(row.payload, dict) else {}
        campaign_id = payload.get("campaign_id")
        if isinstance(campaign_id, str) and campaign_id:
            wanted.append(campaign_id)
    campaigns = {
        str(item.pk): item
        for item in Campaign.objects.filter(pk__in=wanted).only("name", "revision")
    }
    return [_notification_view(row, campaigns) for row in rows]


def mark_notification_read(user, notification_id: object) -> dict[str, object]:
    try:
        key = _as_int(notification_id)
    except (TypeError, ValueError):
        raise CampaignError("not_found") from None
    row = Notification.objects.filter(pk=key, user=user).first()
    if row is None:
        raise CampaignError("not_found")
    if row.read_at is None:
        row.read_at = timezone.now()
        row.save(update_fields=["read_at"])
    return _notification_view(row)


def _notify_campaign_invite(invited, campaign: Campaign, revision: int) -> None:
    Notification.objects.filter(
        user=invited,
        kind=Notification.KIND_CAMPAIGN_INVITE,
        read_at__isnull=True,
        payload__campaign_id=str(campaign.id),
    ).delete()
    Notification.objects.create(
        user=invited,
        kind=Notification.KIND_CAMPAIGN_INVITE,
        payload={
            "campaign_id": str(campaign.id),
            "campaign_name": campaign.name,
            "revision": revision,
        },
    )
    _push_after_commit([invited.pk], {"type": "notification"})


def mark_invite_read(user, campaign_id) -> None:
    """The player took the seat. Only unread invite notes are stamped."""
    Notification.objects.filter(
        user=user,
        kind=Notification.KIND_CAMPAIGN_INVITE,
        read_at__isnull=True,
        payload__campaign_id=str(campaign_id),
    ).update(read_at=timezone.now())


def _close_invite_notices(row) -> None:
    if row.invited_user_id is None:
        return
    Notification.objects.filter(
        user_id=row.invited_user_id,
        kind=Notification.KIND_CAMPAIGN_INVITE,
        payload__campaign_id=str(row.campaign_id),
    ).update(read_at=timezone.now())


def _notification_view(row, campaigns: dict[str, Campaign] | None = None) -> dict[str, object]:
    payload = row.payload if isinstance(row.payload, dict) else {}
    if row.kind == Notification.KIND_CAMPAIGN_INVITE:
        campaign_id = payload.get("campaign_id")
        campaign = None
        if isinstance(campaign_id, str) and campaign_id:
            if campaigns is not None:
                campaign = campaigns.get(campaign_id)
            else:
                campaign = Campaign.objects.filter(pk=campaign_id).only("name", "revision").first()
        if campaign is not None:
            payload = {
                **payload,
                "campaign_name": campaign.name,
                "revision": campaign.revision,
            }
    return {
        "id": str(row.pk),
        "kind": row.kind,
        "payload": payload,
        "created_at": row.created_at.isoformat(),
        "read": row.read_at is not None,
    }


def record_promotions(campaign: Campaign, name: str, user_ids: list[int]) -> None:
    for user_id in user_ids:
        Notification.objects.create(
            user_id=user_id,
            kind=Notification.KIND_CAMPAIGN_ADMIN,
            payload={"campaign_id": str(campaign.id), "campaign_name": name},
        )
    if user_ids:
        _push_after_commit(user_ids, {"type": "notification"})


def notify_battles(campaign: Campaign, game, opened: list) -> None:
    now = timezone.now()
    recipients: list[int] = []
    for member in game.members:
        if member.status not in {"active", "eliminated"} or not member.player_id.isdigit():
            continue
        try:
            shown = project(game, member.player_id, now)
        except DomainError:
            continue
        raw_battles = shown.get("battles", [])
        battles = raw_battles if isinstance(raw_battles, list) else []
        visible = {
            item.get("id")
            for item in battles
            if isinstance(item, dict)
        }
        for battle in opened:
            if battle.id not in visible:
                continue
            Notification.objects.create(
                user_id=int(member.player_id),
                kind=Notification.KIND_CAMPAIGN_BATTLE,
                payload={
                    "campaign_id": str(campaign.id),
                    "campaign_name": game.name,
                    "battle_id": battle.id,
                },
            )
            recipients.append(int(member.player_id))
    if recipients:
        _push_after_commit(recipients, {"type": "notification"})
