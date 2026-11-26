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


def store_drawn(
    user,
    name: str,
    size: int,
    cells: list[dict[str, object]],
    anchors: list[dict[str, object]] | None = None,
) -> CampaignMap:
    try:
        template = drawn(size, cells, anchors)
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
            generated=False,
            document=dump_template(template),
        )


def update_drawn(
    user,
    map_id: str,
    name: str,
    size: int,
    cells: list[dict[str, object]],
    anchors: list[dict[str, object]] | None = None,
) -> CampaignMap:
    try:
        template = drawn(size, cells, anchors)
        title = campaign_name(name)
    except DomainError as exc:
        raise CampaignError(exc.code) from exc
    with transaction.atomic():
        _actor(user)
        row = _owned(user, map_id)
        if row.generated:
            raise CampaignError("map_readonly")
        row.name = title
        row.size = template.size
        row.seats = template.seats
        row.document = dump_template(template)
        row.save(update_fields=["name", "size", "seats", "document"])
        return row


def copy_for_edit(user, map_id: str, name: str | None = None) -> CampaignMap:
    """Clone any owned map into a new hand-drawn atlas the player can reshape."""
    with transaction.atomic():
        account = _actor(user)
        source = _owned(user, map_id)
        try:
            template = load_template(source.document)
            title = campaign_name(name or f"{source.name} · copia")
            clone = drawn(
                template.size,
                [
                    {
                        "q": cell.q,
                        "r": cell.r,
                        "ground": plot.ground,
                        "road": plot.road,
                        "bridge": plot.bridge,
                    }
                    for cell, plot in template.cells.items()
                ],
                [{"q": cell.q, "r": cell.r} for cell in template.anchors],
            )
        except DomainError as exc:
            raise CampaignError(exc.code) from exc
        _ensure_room(account)
        return CampaignMap.objects.create(
            owner=account,
            name=title,
            size=clone.size,
            seats=clone.seats,
            generated=False,
            document=dump_template(clone),
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
