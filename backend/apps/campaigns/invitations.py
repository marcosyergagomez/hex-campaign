"""Alias invites and secret links. The match document is only loaded to change it."""

from __future__ import annotations

import re
import secrets

from django.db import transaction
from django.utils import timezone

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game, require_owner, require_phase, require_staff, seated
from hexcampaign.domain.lobby import accept_seat, invite_player

from .access import (
    _actor,
    _digest,
    _document,
    _lock_accounts,
    _locked,
    _player_by_alias,
    _require_account,
    _staff_campaign,
)
from .errors import CampaignError, RevisionConflict
from .match import _assert_running_capacity, _mutate
from .models import Campaign, Invitation
from .notices import _as_int, _close_invite_notices, _notify_campaign_invite, mark_invite_read
from .queries import card
from .store import _save


def invite_alias(user, campaign_id, revision: int, alias: str) -> tuple[Campaign, Game]:
    invited = _player_by_alias(alias)
    if invited is None or not invited.is_active or invited.email_verified_at is None:
        raise CampaignError("unknown_player")
    if invited.pk == user.pk:
        raise CampaignError("forbidden")

    def command(game: Game) -> Game:
        return invite_player(game, str(user.pk), str(invited.pk), invited.alias)

    with transaction.atomic():
        # Inviter and invitee before the campaign. play() uses the same order.
        locked = _lock_accounts([user.pk, invited.pk])
        _require_account(locked, user)
        try:
            _assert_running_capacity(invited, campaign_id)
        except CampaignError as exc:
            if exc.code == "campaign_limit":
                raise CampaignError("invitee_campaign_limit") from exc
            raise
        campaign = _locked(campaign_id)
        pending = (
            Invitation.objects.select_for_update()
            .filter(
                campaign=campaign,
                invited_user=invited,
                accepted_at__isnull=True,
                declined_at__isnull=True,
                revoked_at__isnull=True,
            )
            .first()
        )
        if pending is not None:
            # Already invited: do not bump revision or spam notifications/SSE.
            game = _document(campaign)
            if game.revision != revision:
                raise RevisionConflict()
            try:
                require_staff(game, str(user.pk))
            except DomainError as exc:
                raise CampaignError(exc.code) from exc
            return campaign, game
        closed = (
            Invitation.objects.select_for_update()
            .filter(campaign=campaign, invited_user=invited, accepted_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if closed is not None:
            game = _document(campaign)
            if game.revision != revision:
                raise RevisionConflict()
            try:
                require_staff(game, str(user.pk))
            except DomainError as exc:
                raise CampaignError(exc.code) from exc
            closed.declined_at = None
            closed.revoked_at = None
            closed.save(update_fields=["declined_at", "revoked_at"])
            _notify_campaign_invite(invited, campaign, game.revision)
            return campaign, game
        campaign, game = _mutate(campaign, revision, command)
        Invitation.objects.create(
            campaign=campaign,
            token_hash=_digest(secrets.token_urlsafe(32)),
            invited_user=invited,
        )
        _notify_campaign_invite(invited, campaign, game.revision)
        return campaign, game


def list_invitations(user, campaign_id) -> list[dict[str, str]]:
    """Staff see each alias invite: pending, accepted, declined by the player, or revoked."""
    campaign = _staff_campaign(user, campaign_id)
    rows = (
        Invitation.objects.filter(campaign=campaign, invited_user__isnull=False)
        .select_related("invited_user")
        .only(
            "accepted_at",
            "declined_at",
            "revoked_at",
            "invited_user__alias",
        )
        .order_by("-created_at")
    )
    shown: list[dict[str, str]] = []
    for row in rows:
        account = row.invited_user
        shown.append(
            {
                "id": str(row.pk),
                "alias": account.alias if account is not None else "",
                "status": _invitation_status(row),
            }
        )
    return shown


def revoke_invitation(user, campaign_id, invitation_id: object) -> None:
    row = _staff_invitation(user, campaign_id, invitation_id)[0]
    if row.accepted_at is not None or row.revoked_at is not None:
        raise CampaignError("invitation_invalid")
    row.revoked_at = timezone.now()
    row.save(update_fields=["revoked_at"])
    _close_invite_notices(row)


def resend_invitation(user, campaign_id, invitation_id: object) -> None:
    row, campaign = _staff_invitation(user, campaign_id, invitation_id)
    if row.accepted_at is not None or row.invited_user is None:
        raise CampaignError("invitation_invalid")
    row.declined_at = None
    row.revoked_at = None
    row.save(update_fields=["declined_at", "revoked_at"])
    _notify_campaign_invite(row.invited_user, campaign, campaign.revision)


def decline_invitation(user, campaign_id) -> None:
    """The invited player turns the offer down. Staff can see that it was declined."""
    row = (
        Invitation.objects.filter(
            campaign_id=campaign_id,
            invited_user=user,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            declined_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if row is None:
        raise CampaignError("invitation_invalid")
    row.declined_at = timezone.now()
    row.save(update_fields=["declined_at"])
    _close_invite_notices(row)


def invite_link(user, campaign_id) -> str:
    raw = secrets.token_urlsafe(32)
    with transaction.atomic():
        _actor(user)
        campaign = _locked(campaign_id)
        game = _document(campaign)
        try:
            require_owner(game, str(user.pk))
            require_phase(game, "recruiting")
            if len(seated(game)) >= game.rules.seats:
                raise DomainError("seat_full")
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
        Invitation.objects.create(campaign=campaign, token_hash=_digest(raw))
    return raw


def accept_link(user, token: str, revision: int) -> tuple[Campaign, Game]:
    if not isinstance(token, str) or not token or len(token) > 128:
        raise CampaignError("invitation_invalid")
    found = Invitation.objects.filter(
        token_hash=_digest(token),
        accepted_at__isnull=True,
        declined_at__isnull=True,
        revoked_at__isnull=True,
    ).first()
    if found is None or found.invited_user_id not in {None, user.pk}:
        raise CampaignError("invitation_invalid")
    return _accept(user, found.pk, revision)


def accept_alias(user, campaign_id, revision: int) -> tuple[Campaign, Game]:
    with transaction.atomic():
        account = _actor(user)
        campaign = _locked(campaign_id)
        found = (
            Invitation.objects.select_for_update()
            .filter(
                campaign=campaign,
                invited_user=account,
                accepted_at__isnull=True,
                declined_at__isnull=True,
                revoked_at__isnull=True,
            )
            .first()
        )
        if found is None:
            raise CampaignError("invitation_invalid")
        return _accept_locked(account, campaign, found, revision)


def preview_link(user, token: str) -> dict[str, object]:
    if not isinstance(token, str) or not token or len(token) > 128:
        raise CampaignError("invitation_invalid")
    found = (
        Invitation.objects.select_related("campaign")
        .defer("campaign__state")
        .filter(
            token_hash=_digest(token),
            accepted_at__isnull=True,
            declined_at__isnull=True,
            revoked_at__isnull=True,
        )
        .first()
    )
    if found is None or found.invited_user_id not in {None, user.pk}:
        raise CampaignError("invitation_invalid")
    return card(found.campaign)


def search_players(user, query: object) -> list[dict[str, str]]:
    from apps.accounts.models import User

    if not isinstance(query, str):
        return []
    needle = query.strip()
    # Two characters minimum slows alias enumeration without hurting lobby search.
    if len(needle) < 2 or len(needle) > 24 or not re.fullmatch(r"[A-Za-z0-9_]+", needle):
        return []
    from apps.accounts.throttle import account_posts

    key = f"player-search:{user.pk}"
    if not account_posts.allow(key, limit=30, window_seconds=60):
        raise CampaignError("search_limited")
    rows = (
        User.objects.filter(
            is_active=True,
            email_verified_at__isnull=False,
            alias__istartswith=needle,
        )
        .exclude(pk=user.pk)
        .order_by("alias")[:12]
    )
    return [{"alias": row.alias} for row in rows]


def _staff_invitation(user, campaign_id, invitation_id: object):
    try:
        key = _as_int(invitation_id)
    except (TypeError, ValueError):
        raise CampaignError("invitation_invalid") from None
    campaign = _staff_campaign(user, campaign_id)
    row = Invitation.objects.filter(pk=key, campaign=campaign).first()
    if row is None:
        raise CampaignError("invitation_invalid")
    return row, campaign


def _invitation_status(row) -> str:
    if row.accepted_at is not None:
        return "accepted"
    if row.revoked_at is not None:
        return "revoked"
    if row.declined_at is not None:
        return "declined"
    return "pending"


def _accept(user, invitation_id: int, revision: int) -> tuple[Campaign, Game]:
    with transaction.atomic():
        # Lock the account, then the campaign, then the invite.
        account = _actor(user)
        try:
            peek = Invitation.objects.get(pk=invitation_id)
        except Invitation.DoesNotExist:
            raise CampaignError("invitation_invalid") from None
        campaign = _locked(peek.campaign_id)
        found = Invitation.objects.select_for_update().get(pk=invitation_id)
        if (
            found.accepted_at is not None
            or found.declined_at is not None
            or found.revoked_at is not None
            or found.invited_user_id not in {None, account.pk}
        ):
            raise CampaignError("invitation_invalid")
        return _accept_locked(account, campaign, found, revision)


def _accept_locked(
    account,
    campaign: Campaign,
    found: Invitation,
    revision: int,
) -> tuple[Campaign, Game]:
    game = _document(campaign)
    if game.revision != revision:
        raise RevisionConflict()
    try:
        updated = accept_seat(game, str(account.pk), account.alias)
    except DomainError as exc:
        raise CampaignError(exc.code) from exc
    found.accepted_at = timezone.now()
    found.save(update_fields=["accepted_at"])
    mark_invite_read(account, campaign.id)
    _save(campaign, updated)
    return campaign, updated
