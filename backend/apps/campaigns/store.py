"""Persist one document and mirror its seats. Callers already hold the row lock."""

from __future__ import annotations

from django.db import transaction

from hexcampaign.domain.game import Game, to_dict

from .access import _push_after_commit
from .models import Campaign, Seat
from .notices import notify_battles, record_promotions


def _save(campaign: Campaign, game: Game) -> None:
    previous = _member_roles(campaign.state)
    known_battles = _battle_ids(campaign.state)
    campaign.name = game.name
    campaign.state = to_dict(game)
    campaign.save(update_fields=["name", "state", "updated_at"])
    _sync(campaign, game)
    appointed = [
        int(member.player_id)
        for member in game.members
        if member.role == "admin"
        and previous.get(member.player_id) == "player"
        and member.player_id.isdigit()
    ]
    record_promotions(campaign, game.name, appointed)
    opened = [
        battle
        for battle in game.battles
        if battle.id not in known_battles and battle.result is None and not battle.reverted
    ]
    if opened:
        # Projecting every seat walks the atlas. Do it after the row lock drops.
        pending_campaign = campaign
        pending_game = game
        pending_opened = list(opened)

        def notify_opened() -> None:
            notify_battles(pending_campaign, pending_game, pending_opened)

        transaction.on_commit(notify_opened)
    watchers = [
        int(member.player_id)
        for member in game.members
        if member.status in {"active", "eliminated"} and member.player_id.isdigit()
    ]
    _push_after_commit(
        watchers,
        {
            "type": "campaign",
            "campaign_id": str(campaign.id),
            "revision": game.revision,
            "phase": game.phase,
            "seats": [
                {
                    "player_id": member.player_id,
                    "color": member.color,
                    "ready": member.player_id in game.lobby_ready,
                }
                for member in game.members
            ],
        },
    )
    _push_after_commit(watchers, {"type": "campaigns", "campaign_id": str(campaign.id)})


def _sync(campaign: Campaign, game: Game) -> None:
    """Mirror seats. A road click rewrites the document but usually not the seats."""
    existing = {row.user_id: row for row in Seat.objects.filter(campaign=campaign)}
    seen: list[int] = []
    for member in game.members:
        user_id = int(member.player_id)
        seen.append(user_id)
        current = existing.get(user_id)
        if current is None:
            Seat.objects.create(
                campaign=campaign,
                user_id=user_id,
                alias=member.alias,
                role=member.role,
                status=member.status,
            )
            continue
        if (
            current.alias == member.alias
            and current.role == member.role
            and current.status == member.status
        ):
            continue
        current.alias = member.alias
        current.role = member.role
        current.status = member.status
        current.save(update_fields=["alias", "role", "status"])
    seen_ids = set(seen)
    stale = [user_id for user_id in existing if user_id not in seen_ids]
    if stale:
        Seat.objects.filter(campaign=campaign, user_id__in=stale).delete()


def _battle_ids(state: object) -> set[str]:
    if not isinstance(state, dict):
        return set()
    battles = state.get("battles")
    if not isinstance(battles, list):
        return set()
    found: set[str] = set()
    for battle in battles:
        if isinstance(battle, dict) and isinstance(battle.get("id"), str):
            found.add(battle["id"])
    return found


def _member_roles(state: object) -> dict[str, str]:
    if not isinstance(state, dict):
        return {}
    members = state.get("members")
    if not isinstance(members, list):
        return {}
    roles: dict[str, str] = {}
    for member in members:
        if not isinstance(member, dict):
            continue
        player_id = member.get("player_id")
        role = member.get("role")
        if isinstance(player_id, str) and isinstance(role, str):
            roles[player_id] = role
    return roles
