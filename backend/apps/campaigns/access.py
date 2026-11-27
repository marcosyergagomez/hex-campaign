"""Row locks and document loads. Lists do not come through here."""

from __future__ import annotations

import hashlib
import logging
import uuid

from django.db import transaction

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game, from_dict

from .errors import CampaignError
from .live import live_bus
from .models import Campaign, Seat

log = logging.getLogger("hexcampaign.campaigns")


def _actor(user):
    locked = _lock_accounts([user.pk])
    return _require_account(locked, user)


def _lock_accounts(user_ids: list[int]) -> dict[int, object]:
    """Lock account rows in primary-key order. Never lock a campaign first."""
    from apps.accounts.models import User

    locked: dict[int, object] = {}
    for pk in sorted({int(user_id) for user_id in user_ids}):
        row = User.objects.select_for_update().filter(pk=pk).first()
        if row is not None:
            locked[pk] = row
    return locked


def _require_account(locked: dict[int, object], user):
    from apps.accounts.models import User

    account = locked.get(user.pk)
    if (
        not isinstance(account, User)
        or not account.is_active
        or account.email_verified_at is None
    ):
        raise CampaignError("account_inactive")
    return account


def _player_by_alias(alias: str):
    from apps.accounts.models import User
    from apps.accounts.validation import canonical_alias

    if not isinstance(alias, str):
        return None
    return User.objects.filter(alias__iexact=canonical_alias(alias)).first()


def _campaign(campaign_id) -> Campaign:
    try:
        key = uuid.UUID(str(campaign_id))
    except ValueError:
        raise CampaignError("not_found") from None
    try:
        return Campaign.objects.get(pk=key)
    except Campaign.DoesNotExist:
        raise CampaignError("not_found") from None


def _locked(campaign_id) -> Campaign:
    try:
        key = uuid.UUID(str(campaign_id))
    except ValueError:
        raise CampaignError("not_found") from None
    try:
        return Campaign.objects.select_for_update().get(pk=key)
    except Campaign.DoesNotExist:
        raise CampaignError("not_found") from None


def _document(campaign: Campaign) -> Game:
    try:
        return from_dict(campaign.state)
    except DomainError as exc:
        log.warning("campaign document rejected id=%s code=%s", campaign.id, exc.code)
        raise CampaignError(exc.code) from exc


def _readable_campaign(user, campaign_id) -> Campaign:
    """A seated player who has not been expelled. Does not load the document."""
    return _member_campaign(user, campaign_id, staff=False)


def _staff_campaign(user, campaign_id) -> Campaign:
    """Active owner or admin, still without opening the document."""
    return _member_campaign(user, campaign_id, staff=True)


def _member_campaign(user, campaign_id, *, staff: bool) -> Campaign:
    try:
        key = uuid.UUID(str(campaign_id))
    except ValueError:
        raise CampaignError("not_found") from None
    campaign = Campaign.objects.filter(pk=key).defer("state").first()
    if campaign is None:
        raise CampaignError("not_found")
    seat = (
        Seat.objects.filter(campaign_id=key, user_id=user.pk).only("role", "status").first()
    )
    if seat is None or seat.status == "expelled":
        raise CampaignError("forbidden")
    if staff and (seat.role not in {"owner", "admin"} or seat.status != "active"):
        raise CampaignError("forbidden")
    return campaign


def _seat_user_ids(campaign: Campaign) -> list[int]:
    return list(Seat.objects.filter(campaign=campaign).values_list("user_id", flat=True))


def _push_after_commit(user_ids: list[int], event: dict[str, object]) -> None:
    recipients = list(dict.fromkeys(int(user_id) for user_id in user_ids))
    if not recipients:
        return
    payload = dict(event)

    def deliver() -> None:
        live_bus.publish_users(recipients, payload)

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(deliver)
    else:
        deliver()


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
