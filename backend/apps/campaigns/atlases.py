"""Save a map the player can reuse. The campaign stores a copy, not a link."""

import random

from django.db import transaction

from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.maps import drawn, dump_template, generate, load_template
from hexcampaign.domain.rules import campaign_name

from .models import CampaignMap
from .records import CampaignError, _actor


def store_generated(user, name: str, size: int, seats: int, rng: random.Random) -> CampaignMap:
    with transaction.atomic():
        account = _actor(user)
        try:
            template = generate(size, seats, rng)
            title = campaign_name(name)
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
        return CampaignMap.objects.create(
            owner=account,
            name=title,
            size=template.size,
            seats=template.seats,
            generated=True,
            document=dump_template(template),
        )


def store_drawn(user, name: str, size: int, cells: list[dict[str, object]]) -> CampaignMap:
    with transaction.atomic():
        account = _actor(user)
        try:
            template = drawn(size, cells)
            title = campaign_name(name)
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
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


def take_template(user, map_id: str):
    return load_template(_owned(user, map_id).document)


def _owned(user, map_id: str) -> CampaignMap:
    try:
        return CampaignMap.objects.get(pk=map_id, owner=user)
    except (CampaignMap.DoesNotExist, ValueError):
        raise CampaignError("map_unknown") from None
