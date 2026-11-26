"""Save a map the player can reuse. The campaign stores a copy, not a link."""

import random
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.map_document import drawn, dump_template, load_template
from hexcampaign.domain.maps import generate
from hexcampaign.domain.rules import campaign_name

from .models import CampaignMap
from .records import CampaignError, _actor

# Keeps atlas storage bounded per account; campaigns already copy the ground.
_MAP_LIMIT = 40


def store_generated(user, name: str, size: int, seats: int, rng: random.Random) -> CampaignMap:
    try:
        template = generate(size, seats, rng)
        title = campaign_name(name)
    except DomainError as exc:
        raise CampaignError(exc.code) from exc
    with transaction.atomic():
        account = _actor(user)
        _ensure_room(account)
        return CampaignMap.objects.create(
            owner=account,
            name=title,
            size=template.size,
            seats=template.seats,
            generated=True,
            document=dump_template(template),
        )


def store_drawn(user, name: str, size: int, cells: list[dict[str, object]]) -> CampaignMap:
    try:
        template = drawn(size, cells)
        title = campaign_name(name)
    except DomainError as exc:
        raise CampaignError(exc.code) from exc
    with transaction.atomic():
        account = _actor(user)
        _ensure_room(account)
        return CampaignMap.objects.create(
            owner=account,
            name=title,
            size=template.size,
            seats=None,
            generated=False,
            document=dump_template(template),
        )


def list_maps(user) -> list[dict[str, object]]:
    rows = CampaignMap.objects.filter(owner=user).defer("document")
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "size": row.size,
            "seats": row.seats,
            "generated": row.generated,
        }
        for row in rows
    ]


def read_map(user, map_id: str) -> dict[str, object]:
    row = _owned(user, map_id)
    return {"id": str(row.id), "name": row.name, **row.document}


def drop_map(user, map_id: str) -> None:
    """Remove a saved atlas. Campaigns already hold their own copy of the ground."""
    with transaction.atomic():
        _actor(user)
        row = _owned(user, map_id)
        row.delete()


def take_template(user, map_id: str):
    return load_template(_owned(user, map_id).document)


def _owned(user, map_id: str) -> CampaignMap:
    try:
        uuid.UUID(str(map_id))
        return CampaignMap.objects.get(pk=map_id, owner=user)
    except (CampaignMap.DoesNotExist, ValueError, TypeError, ValidationError):
        raise CampaignError("map_unknown") from None


def _ensure_room(account) -> None:
    if CampaignMap.objects.filter(owner=account).count() >= _MAP_LIMIT:
        raise CampaignError("map_limit")
