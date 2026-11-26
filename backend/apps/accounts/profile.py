"""Update the signed-in player's public profile fields."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import translation

from apps.accounts.models import User
from apps.accounts.validation import (
    MAX_PASSWORD_LENGTH,
    PASSWORD_TOO_LONG,
    SEX_MESSAGE,
    Sex,
    alias_errors,
    canonical_alias,
)


class ProfileRejected(Exception):
    def __init__(self, errors: dict[str, list[str]]) -> None:
        self.errors = errors
        super().__init__("profile")


def public_profile(user: User) -> dict[str, str]:
    return {
        "email": user.email,
        "alias": user.alias,
        "sex": user.sex,
        "birth_date": user.birth_date.isoformat(),
    }


def update_profile(
    user: User,
    *,
    alias: object,
    sex: object,
    password: object = None,
    current_password: object = None,
) -> User:
    errors: dict[str, list[str]] = {}
    if not isinstance(alias, str):
        errors["alias"] = alias_errors("").get("alias", ["El alias no es válido."])
    else:
        next_alias = canonical_alias(alias)
        errors.update(alias_errors(next_alias))
        taken = (
            User.objects.annotate(alias_key=Lower("alias"))
            .filter(alias_key=next_alias.lower())
            .exclude(pk=user.pk)
            .exists()
        )
        if taken:
            errors["alias"] = ["Ese alias ya está en uso."]

    if not isinstance(sex, str) or sex not in Sex.values:
        errors["sex"] = [SEX_MESSAGE]

    changing_password = password not in (None, "")
    if changing_password:
        if not isinstance(current_password, str) or not user.check_password(current_password):
            errors["current_password"] = ["La contraseña actual no es correcta."]
        if not isinstance(password, str):
            errors["password"] = [PASSWORD_TOO_LONG]
        elif len(password) > MAX_PASSWORD_LENGTH:
            errors["password"] = [PASSWORD_TOO_LONG]
        else:
            try:
                with translation.override("es"):
                    validate_password(password, user=user)
            except ValidationError as exc:
                errors["password"] = list(exc.messages)

    if errors:
        raise ProfileRejected(errors)

    assert isinstance(alias, str) and isinstance(sex, str)
    next_alias = canonical_alias(alias)
    with transaction.atomic():
        user.alias = next_alias
        user.sex = sex
        if changing_password:
            assert isinstance(password, str)
            user.set_password(password)
            user.save()
        else:
            user.save(update_fields=["alias", "sex"])
        _mirror_alias(user)
    return user


def _mirror_alias(user: User) -> None:
    """Keep seat rows and living campaign documents in sync with the account alias."""
    from apps.campaigns.models import Campaign, Seat
    from hexcampaign.domain.errors import DomainError
    from hexcampaign.domain.game import from_dict, to_dict

    Seat.objects.filter(user=user).update(alias=user.alias)
    campaign_ids = Seat.objects.filter(user=user).values_list("campaign_id", flat=True)
    for campaign in Campaign.objects.filter(pk__in=campaign_ids).iterator():
        try:
            game = from_dict(campaign.state)
        except DomainError:
            continue
        changed = False
        for member in game.members:
            if member.player_id == str(user.pk) and member.alias != user.alias:
                member.alias = user.alias
                changed = True
        if changed:
            campaign.state = to_dict(game)
            campaign.save(update_fields=["state", "updated_at"])
