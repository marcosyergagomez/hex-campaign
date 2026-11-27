"""Commands that change or open one campaign document."""

from __future__ import annotations

import logging
import random
import uuid
from collections.abc import Callable

from django.db import transaction
from django.utils import timezone

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import (
    Game,
    bump,
    find_member,
    from_dict,
    require_owner,
    to_dict,
)
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.lobby import create_game
from hexcampaign.domain.rules import campaign_name, rules_from
from hexcampaign.domain.sight import equalize_fog
from hexcampaign.domain.turn import deactivate_player, leave_campaign, withdraw_player
from hexcampaign.domain.view import project, project_fort_delta, project_roads_delta

from .access import (
    _actor,
    _document,
    _lock_accounts,
    _locked,
    _push_after_commit,
    _require_account,
    _seat_user_ids,
)
from .errors import (
    PREPARED_PHASES,
    RUNNING_CAMPAIGN_LIMIT,
    RUNNING_PHASES,
    CampaignError,
    RevisionConflict,
)
from .models import Campaign, Seat
from .store import _save, _sync

log = logging.getLogger("hexcampaign.campaigns")


def create_campaign(
    user,
    name: str,
    rules: dict,
    template=None,
    blind: bool = False,
    description: str = "",
) -> tuple[Campaign, Game]:
    del blind  # Kept on the API; fog no longer privileges the creator.
    try:
        parsed = rules_from(rules)
    except DomainError as exc:
        raise CampaignError(exc.code) from exc
    with transaction.atomic():
        account = _actor(user)
        try:
            game = create_game(name, parsed, str(account.pk), account.alias, description)
            game.identity_required = True
            if template is not None:
                from hexcampaign.domain.maps import lay

                # Fog binds every seat the same way; the atlas stays sealed until kickoff.
                lay(game, template, None)
                game.surveyor = None
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
        campaign = Campaign.objects.create(
            name=game.name,
            state=to_dict(game),
            created_by=account,
        )
        _sync(campaign, game)
        _push_after_commit(
            [account.pk],
            {"type": "campaigns", "campaign_id": str(campaign.id)},
        )
    return campaign, game


def delete_campaign(user, campaign_id) -> None:
    """Owner may scrap a campaign that has not entered the marching clock yet."""
    with transaction.atomic():
        account = _actor(user)
        campaign = _locked(campaign_id)
        game = _document(campaign)
        try:
            require_owner(game, str(account.pk))
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
        if game.phase not in PREPARED_PHASES:
            raise CampaignError("campaign_delete_locked")
        campaign.delete()


def scrap_campaign(user, campaign_id, confirm_name: object) -> None:
    """Leave or destroy a campaign after typing its name.

    - Owner + prepared: the document is deleted.
    - Owner/admin + running: ownership moves on, the seat leaves the table.
    - Player: the seat becomes inactive (staff may restore or expel).
    """
    try:
        typed = campaign_name(confirm_name)
    except DomainError as exc:
        raise CampaignError("confirm_name_mismatch") from exc
    with transaction.atomic():
        account = _actor(user)
        campaign = _locked(campaign_id)
        game = _document(campaign)
        if typed != game.name:
            raise CampaignError("confirm_name_mismatch")
        actor = str(account.pk)
        member = find_member(game, actor)
        if member is None or member.status != "active":
            raise CampaignError("forbidden")
        if game.phase == "finished":
            raise CampaignError("campaign_delete_locked")
        if game.phase in PREPARED_PHASES and member.role == "owner":
            _scrap_prepared(campaign)
            return
        _leave_running(campaign, game, actor, member.role)


def _scrap_prepared(campaign: Campaign) -> None:
    watchers = _seat_user_ids(campaign)
    campaign_key = str(campaign.id)
    campaign.delete()
    _push_after_commit(
        watchers,
        {"type": "campaigns", "campaign_id": campaign_key, "gone": True},
    )


def _leave_running(campaign: Campaign, game: Game, actor: str, role: str) -> None:
    rng = random.Random()
    now = timezone.now()
    try:
        if role in {"owner", "admin"}:
            updated = leave_campaign(game, actor, rng, now)
        else:
            updated = withdraw_player(game, actor, rng, now)
    except DomainError as exc:
        raise CampaignError(exc.code) from exc
    _save(campaign, updated)


def play(
    user,
    campaign_id,
    revision: int,
    command: Callable[[Game], Game],
) -> tuple[Campaign, Game]:
    with transaction.atomic():
        # Lock every seated account, in primary-key order, before the campaign.
        # The same order as invite and as User.save, so two writes cannot deadlock.
        try:
            key = uuid.UUID(str(campaign_id))
        except ValueError:
            raise CampaignError("not_found") from None
        seat_ids = list(Seat.objects.filter(campaign_id=key).values_list("user_id", flat=True))
        locked = _lock_accounts([*seat_ids, user.pk])
        _require_account(locked, user)
        campaign = _locked(campaign_id)
        return _mutate(campaign, revision, command)


def _mutate(
    campaign: Campaign,
    revision: int,
    command: Callable[[Game], Game],
) -> tuple[Campaign, Game]:
    """Apply a command. Caller already holds the account locks and the campaign row."""
    game = _document(campaign)
    if game.revision != revision:
        raise RevisionConflict()
    before = game.revision
    was_running = campaign.phase in RUNNING_PHASES
    active_before = {member.player_id for member in game.members if member.status == "active"}
    try:
        updated = command(game)
    except DomainError as exc:
        raise CampaignError(exc.code) from exc
    if updated.revision != before:
        if updated.phase in RUNNING_PHASES and not was_running:
            _assert_members_running_capacity(updated, campaign.pk)
        elif updated.phase in RUNNING_PHASES:
            _assert_reactivated_capacity(updated, campaign.pk, active_before)
        _save(campaign, updated)
    return campaign, updated


def _assert_running_capacity(user, campaign_id) -> None:
    """Any active seat may keep at most three campaigns in orders or battles."""
    if user is None:
        return
    running = (
        Seat.objects.filter(user=user, status="active", campaign__phase__in=RUNNING_PHASES)
        .exclude(campaign_id=campaign_id)
        .count()
    )
    if running >= RUNNING_CAMPAIGN_LIMIT:
        raise CampaignError("campaign_limit")


def _assert_members_running_capacity(game: Game, campaign_id) -> None:
    _assert_ids_running_capacity(
        [int(member.player_id) for member in game.members if _countable(member)],
        campaign_id,
    )


def _assert_reactivated_capacity(game: Game, campaign_id, active_before: set[str]) -> None:
    """When staff restores a seat into a running match, count that player's other seats."""
    _assert_ids_running_capacity(
        [
            int(member.player_id)
            for member in game.members
            if _countable(member) and member.player_id not in active_before
        ],
        campaign_id,
    )


def _countable(member) -> bool:
    return member.status == "active" and member.player_id.isdigit()


def _assert_ids_running_capacity(user_ids: list[int], campaign_id) -> None:
    if not user_ids:
        return
    from django.db.models import Count

    crowded = (
        Seat.objects.filter(
            user_id__in=user_ids,
            status="active",
            campaign__phase__in=RUNNING_PHASES,
        )
        .exclude(campaign_id=campaign_id)
        .values("user_id")
        .annotate(running=Count("pk"))
        .filter(running__gte=RUNNING_CAMPAIGN_LIMIT)
    )
    if crowded.exists():
        raise CampaignError("campaign_limit")


def read_campaign(user, campaign_id, now) -> dict[str, object]:
    try:
        key = uuid.UUID(str(campaign_id))
    except ValueError:
        raise CampaignError("not_found") from None
    # A stranger must not pay for parsing the document.
    seat = (
        Seat.objects.filter(
            campaign_id=key,
            user_id=user.pk,
            status__in=["active", "eliminated"],
        )
        .select_related("campaign")
        .first()
    )
    if seat is None:
        raise CampaignError("not_found")
    campaign = seat.campaign
    game = _document(campaign)
    # Match list_campaigns / pulse: expelled and inactive seats get no live intel.
    if not _readable_member(game, str(user.pk)):
        # Do not leak name, phase or seat counts to anyone who is not seated.
        # Invitation previews go through preview_link with a secret token.
        raise CampaignError("not_found")
    if game.surveyor:
        with transaction.atomic():
            _actor(user)
            campaign = _locked(campaign_id)
            game = _document(campaign)
            if not _readable_member(game, str(user.pk)):
                raise CampaignError("not_found")
            if equalize_fog(game):
                _save(campaign, bump(game))
    return present(campaign, game, user, now)


def _readable_member(game: Game, player_id: str) -> bool:
    member = find_member(game, player_id)
    return member is not None and member.status in {"active", "eliminated"}


def present(campaign: Campaign, game: Game, user, now) -> dict[str, object]:
    body = project(game, str(user.pk), now)
    body["id"] = str(campaign.id)
    body["joined"] = True
    return body


def present_fort_delta(campaign: Campaign, game: Game, user) -> dict[str, object]:
    body = project_fort_delta(game, str(user.pk))
    body["id"] = str(campaign.id)
    body["joined"] = True
    return body


def present_roads_delta(
    campaign: Campaign,
    game: Game,
    user,
    changed: list[Hex],
) -> dict[str, object]:
    body = project_roads_delta(game, str(user.pk), changed)
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
        except DomainError as exc:
            log.warning(
                "campaign document skipped while deactivating account id=%s code=%s",
                campaign_id,
                exc.code,
            )
            continue
        before = game.revision
        updated = deactivate_player(game, str(user_id), rng)
        if updated.revision != before:
            _save(campaign, updated)
