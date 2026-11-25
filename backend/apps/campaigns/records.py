"""Load and store a campaign. The document stays the match; seats mirror its players."""

import hashlib
import random
import secrets
import uuid
from collections.abc import Callable

from django.db import transaction
from django.utils import timezone

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import (
    Game,
    find_member,
    from_dict,
    require_owner,
    require_phase,
    to_dict,
)
from hexcampaign.domain.lobby import accept_seat, create_game, invite_player
from hexcampaign.domain.rules import rules_from
from hexcampaign.domain.turn import deactivate_player
from hexcampaign.domain.view import project

from .models import Campaign, Invitation, Seat


class CampaignError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RevisionConflict(CampaignError):
    def __init__(self) -> None:
        super().__init__("revision_conflict")


OPEN_PHASES = ("recruiting", "placing", "orders", "battles")
OPEN_CAMPAIGN_LIMIT = 3


def create_campaign(
    user,
    name: str,
    rules: dict,
    template=None,
    blind: bool = False,
) -> tuple[Campaign, Game]:
    try:
        parsed = rules_from(rules)
    except DomainError as exc:
        raise CampaignError(exc.code) from exc
    with transaction.atomic():
        account = _actor(user)
        open_campaigns = Campaign.objects.filter(created_by=account, phase__in=OPEN_PHASES).count()
        if open_campaigns >= OPEN_CAMPAIGN_LIMIT:
            raise CampaignError("campaign_limit")
        try:
            game = create_game(name, parsed, str(account.pk), account.alias)
            game.identity_required = True
            if template is not None:
                from hexcampaign.domain.maps import lay

                surveyor = None if template.generated and blind else str(account.pk)
                lay(game, template, surveyor)
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
        campaign = Campaign.objects.create(
            name=game.name,
            state=to_dict(game),
            created_by=account,
        )
        _sync(campaign, game)
    return campaign, game


def play(
    user,
    campaign_id,
    revision: int,
    command: Callable[[Game], Game],
) -> tuple[Campaign, Game]:
    with transaction.atomic():
        # The account row is locked before the campaign, same order as User.save.
        _actor(user)
        campaign = _locked(campaign_id)
        game = _document(campaign)
        if game.revision != revision:
            raise RevisionConflict()
        try:
            updated = command(game)
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
        _save(campaign, updated)
        return campaign, updated


def invite_alias(user, campaign_id, revision: int, alias: str) -> tuple[Campaign, Game]:
    invited = _player_by_alias(alias)
    if invited is None or not invited.is_active or invited.email_verified_at is None:
        raise CampaignError("unknown_player")

    def command(game: Game) -> Game:
        return invite_player(game, str(user.pk), str(invited.pk), invited.alias)

    with transaction.atomic():
        campaign, game = play(user, campaign_id, revision, command)
        Invitation.objects.create(
            campaign=campaign,
            token_hash=_digest(secrets.token_urlsafe(32)),
            invited_user=invited,
        )
        return campaign, game


def invite_link(user, campaign_id) -> str:
    raw = secrets.token_urlsafe(32)
    with transaction.atomic():
        _actor(user)
        campaign = _locked(campaign_id)
        game = _document(campaign)
        try:
            require_owner(game, str(user.pk))
            require_phase(game, "recruiting")
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
        Invitation.objects.create(campaign=campaign, token_hash=_digest(raw))
    return raw


def accept_link(user, token: str, revision: int) -> tuple[Campaign, Game]:
    if not isinstance(token, str) or not token or len(token) > 128:
        raise CampaignError("invitation_invalid")
    found = Invitation.objects.filter(token_hash=_digest(token), accepted_at__isnull=True).first()
    if found is None or found.invited_user_id not in {None, user.pk}:
        raise CampaignError("invitation_invalid")
    return _accept(user, found.pk, revision)


def accept_alias(user, campaign_id, revision: int) -> tuple[Campaign, Game]:
    with transaction.atomic():
        account = _actor(user)
        campaign = _locked(campaign_id)
        found = (
            Invitation.objects.select_for_update()
            .filter(campaign=campaign, invited_user=account, accepted_at__isnull=True)
            .first()
        )
        if found is None:
            raise CampaignError("invitation_invalid")
        return _accept_locked(account, campaign, found, revision)


def read_campaign(user, campaign_id, now) -> dict[str, object]:
    campaign = _campaign(campaign_id)
    game = _document(campaign)
    if find_member(game, str(user.pk)) is None:
        return _card(campaign, game)
    return present(campaign, game, user, now)


def list_campaigns(user) -> list[dict[str, object]]:
    seats = Seat.objects.filter(user=user).select_related("campaign").defer("campaign__state")
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
    pending = Invitation.objects.filter(invited_user=user, accepted_at__isnull=True)
    pending = pending.select_related("campaign")
    rows: list[dict[str, object]] = []
    for item in pending:
        state = item.campaign.state if isinstance(item.campaign.state, dict) else {}
        rows.append(
            {
                "id": str(item.campaign_id),
                "name": item.campaign.name,
                "revision": state.get("revision"),
            }
        )
    return rows


def preview_link(user, token: str) -> dict[str, object]:
    if not isinstance(token, str) or not token or len(token) > 128:
        raise CampaignError("invitation_invalid")
    found = Invitation.objects.filter(token_hash=_digest(token), accepted_at__isnull=True).first()
    if found is None or found.invited_user_id not in {None, user.pk}:
        raise CampaignError("invitation_invalid")
    return _card(found.campaign, _document(found.campaign))


def present(campaign: Campaign, game: Game, user, now) -> dict[str, object]:
    body = project(game, str(user.pk), now)
    body["id"] = str(campaign.id)
    body["joined"] = True
    return body


def deactivate_account(user_id: int) -> None:
    """Mark this player's seats inactive. Caller already holds the user row."""
    campaign_ids = Seat.objects.filter(user_id=user_id).exclude(status="expelled")
    identifiers = sorted(campaign_ids.values_list("campaign_id", flat=True), key=str)
    rng = random.Random()
    for campaign_id in identifiers:
        campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
        try:
            game = from_dict(campaign.state)
        except DomainError:
            continue
        before = game.revision
        updated = deactivate_player(game, str(user_id), rng)
        if updated.revision != before:
            _save(campaign, updated)


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
        if found.accepted_at is not None or found.invited_user_id not in {None, account.pk}:
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
    _save(campaign, updated)
    return campaign, updated


def _card(campaign: Campaign, game: Game) -> dict[str, object]:
    from hexcampaign.domain.game import seated

    return {
        "id": str(campaign.id),
        "name": game.name,
        "phase": game.phase,
        "seats": game.rules.seats,
        "occupied": len(seated(game)),
        "revision": game.revision,
        "joined": False,
    }


def _actor(user):
    from apps.accounts.models import User

    account = User.objects.select_for_update().filter(pk=user.pk).first()
    if account is None or not account.is_active or account.email_verified_at is None:
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
        raise CampaignError(exc.code) from exc


def _save(campaign: Campaign, game: Game) -> None:
    campaign.name = game.name
    campaign.state = to_dict(game)
    campaign.save(update_fields=["name", "state", "updated_at"])
    _sync(campaign, game)


def _sync(campaign: Campaign, game: Game) -> None:
    seen: list[int] = []
    for member in game.members:
        user_id = int(member.player_id)
        Seat.objects.update_or_create(
            campaign=campaign,
            user_id=user_id,
            defaults={"alias": member.alias, "role": member.role, "status": member.status},
        )
        seen.append(user_id)
    Seat.objects.filter(campaign=campaign).exclude(user_id__in=seen).delete()


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
