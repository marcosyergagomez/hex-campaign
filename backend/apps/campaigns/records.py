"""Load and store a campaign. The document stays the match; seats mirror its players."""

import hashlib
import random
import re
import secrets
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
    require_phase,
    require_staff,
    seated,
    to_dict,
)
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.lobby import accept_seat, create_game, invite_player
from hexcampaign.domain.rules import campaign_name, rules_from
from hexcampaign.domain.sight import equalize_fog
from hexcampaign.domain.turn import (
    deactivate_player,
    leave_campaign,
    restore_player,
    withdraw_player,
)
from hexcampaign.domain.view import project, project_roads_delta

from .live import live_bus
from .models import Campaign, Invitation, Seat


class CampaignError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RevisionConflict(CampaignError):
    def __init__(self) -> None:
        super().__init__("revision_conflict")


# Visible lifecycle: prepared (recruiting/placing/preparing), running, finished.
PREPARED_PHASES = ("recruiting", "placing", "preparing")
RUNNING_PHASES = ("orders", "battles")
RUNNING_CAMPAIGN_LIMIT = 3


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
        # The account row is locked before the campaign, same order as User.save.
        _actor(user)
        campaign = _locked(campaign_id)
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
    from apps.accounts.models import User

    for member in game.members:
        if member.status != "active":
            continue
        try:
            account = User.objects.get(pk=int(member.player_id))
        except (TypeError, ValueError, User.DoesNotExist):
            continue
        _assert_running_capacity(account, campaign_id)


def _assert_reactivated_capacity(game: Game, campaign_id, active_before: set[str]) -> None:
    """When staff restores a seat into a running match, count that player's other seats."""
    from apps.accounts.models import User

    for member in game.members:
        if member.status != "active" or member.player_id in active_before:
            continue
        try:
            account = User.objects.get(pk=int(member.player_id))
        except (TypeError, ValueError, User.DoesNotExist):
            continue
        _assert_running_capacity(account, campaign_id)


def invite_alias(user, campaign_id, revision: int, alias: str) -> tuple[Campaign, Game]:
    invited = _player_by_alias(alias)
    if invited is None or not invited.is_active or invited.email_verified_at is None:
        raise CampaignError("unknown_player")
    if invited.pk == user.pk:
        raise CampaignError("forbidden")

    def command(game: Game) -> Game:
        return invite_player(game, str(user.pk), str(invited.pk), invited.alias)

    with transaction.atomic():
        try:
            _assert_running_capacity(invited, campaign_id)
        except CampaignError as exc:
            if exc.code == "campaign_limit":
                raise CampaignError("invitee_campaign_limit") from exc
            raise
        campaign = _locked(campaign_id)
        pending = (
            Invitation.objects.select_for_update()
            .filter(campaign=campaign, invited_user=invited, accepted_at__isnull=True)
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
        campaign, game = play(user, campaign_id, revision, command)
        Invitation.objects.create(
            campaign=campaign,
            token_hash=_digest(secrets.token_urlsafe(32)),
            invited_user=invited,
        )
        _notify_campaign_invite(invited, campaign, game.revision)
        return campaign, game


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
    if not account_posts.allow(key, limit=30, window=60):
        return []
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


def list_notifications(user) -> list[dict[str, object]]:
    from .models import Notification

    rows = Notification.objects.filter(user=user).order_by("-created_at")[:40]
    return [_notification_view(row) for row in rows]


def mark_notification_read(user, notification_id: object) -> dict[str, object]:
    from .models import Notification

    try:
        key = int(notification_id)
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
    from .models import Notification

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


def _notification_view(row) -> dict[str, object]:
    from .models import Notification

    payload = row.payload if isinstance(row.payload, dict) else {}
    if row.kind == Notification.KIND_CAMPAIGN_INVITE:
        campaign_id = payload.get("campaign_id")
        if isinstance(campaign_id, str) and campaign_id:
            campaign = Campaign.objects.filter(pk=campaign_id).only("name", "state").first()
            if campaign is not None:
                state = campaign.state if isinstance(campaign.state, dict) else {}
                revision = state.get("revision")
                payload = {
                    **payload,
                    "campaign_name": campaign.name,
                    "revision": revision if isinstance(revision, int) else payload.get("revision"),
                }
    return {
        "id": str(row.pk),
        "kind": row.kind,
        "payload": payload,
        "created_at": row.created_at.isoformat(),
        "read": row.read_at is not None,
    }


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


def campaign_pulse(user, campaign_id) -> dict[str, object]:
    """Cheap revision check so clients can refresh when another player acts."""
    seated = Seat.objects.filter(
        campaign_id=campaign_id,
        user=user,
        status__in=["active", "eliminated"],
    ).exists()
    if not seated:
        raise CampaignError("not_found")
    campaign = Campaign.objects.filter(pk=campaign_id).only("phase", "state").first()
    if campaign is None:
        raise CampaignError("not_found")
    state = campaign.state if isinstance(campaign.state, dict) else {}
    revision = state.get("revision")
    if not isinstance(revision, int) or revision < 1:
        raise CampaignError("not_found")
    return {"revision": revision, "phase": campaign.phase}


def list_campaigns(user) -> list[dict[str, object]]:
    # Inactive / expelled seats stay off the player's board until staff restores them.
    seats = (
        Seat.objects.filter(user=user, status__in=["active", "eliminated"])
        .select_related("campaign")
        .defer("campaign__state")
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
    from .models import Notification

    game = _document(campaign)
    if game.revision != revision:
        raise RevisionConflict()
    try:
        updated = accept_seat(game, str(account.pk), account.alias)
    except DomainError as exc:
        raise CampaignError(exc.code) from exc
    found.accepted_at = timezone.now()
    found.save(update_fields=["accepted_at"])
    Notification.objects.filter(
        user=account,
        kind=Notification.KIND_CAMPAIGN_INVITE,
        read_at__isnull=True,
        payload__campaign_id=str(campaign.id),
    ).update(read_at=timezone.now())
    _save(campaign, updated)
    return campaign, updated


def _card(campaign: Campaign, game: Game) -> dict[str, object]:
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
    watchers = [
        int(member.player_id)
        for member in game.members
        if member.status in {"active", "eliminated", "inactive"}
    ]
    _push_after_commit(
        watchers,
        {
            "type": "campaign",
            "campaign_id": str(campaign.id),
            "revision": game.revision,
            "phase": game.phase,
        },
    )
    _push_after_commit(watchers, {"type": "campaigns", "campaign_id": str(campaign.id)})


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


def _seat_user_ids(campaign: Campaign) -> list[int]:
    return list(Seat.objects.filter(campaign=campaign).values_list("user_id", flat=True))


def _push_after_commit(user_ids: list[int], event: dict[str, object]) -> None:
    recipients = list(dict.fromkeys(int(user_id) for user_id in user_ids))
    if not recipients:
        return
    payload = dict(event)

    def deliver() -> None:
        live_bus.publish_users(recipients, payload)

    transaction.on_commit(deliver)


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
