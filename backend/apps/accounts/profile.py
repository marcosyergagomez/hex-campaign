"""Update the signed-in player's public profile fields."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import translation

from apps.accounts.models import User
from apps.accounts.passwords import check_user_password, set_user_password
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


class ProfileUpdate:
    """Saved row plus whether the password (and thus every cookie) changed."""

    def __init__(self, user: User, *, password_changed: bool) -> None:
        self.user = user
        self.password_changed = password_changed


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
) -> ProfileUpdate:
    errors: dict[str, list[str]] = {}
    next_alias = ""
    if not isinstance(alias, str):
        errors["alias"] = alias_errors("").get("alias", ["El alias no es válido."])
    else:
        next_alias = canonical_alias(alias)
        errors.update(alias_errors(next_alias))

    if not isinstance(sex, str) or sex not in Sex.values:
        errors["sex"] = [SEX_MESSAGE]

    changing_password = password not in (None, "")
    if changing_password:
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
        if not isinstance(current_password, str) or not current_password:
            errors.setdefault("current_password", ["La contraseña actual no es correcta."])

    if errors and not changing_password:
        raise ProfileRejected(errors)

    with transaction.atomic():
        locked = User.objects.select_for_update().filter(pk=user.pk).first()
        if locked is None or not locked.is_active or locked.email_verified_at is None:
            raise ProfileRejected({"session": ["La sesión no es válida."]})

        if next_alias and "alias" not in errors:
            taken = (
                User.objects.annotate(alias_key=Lower("alias"))
                .filter(alias_key=next_alias.lower())
                .exclude(pk=locked.pk)
                .exists()
            )
            if taken:
                errors["alias"] = ["Ese alias ya está en uso."]

        if changing_password and "current_password" not in errors:
            assert isinstance(current_password, str)
            if not check_user_password(locked, current_password):
                errors["current_password"] = ["La contraseña actual no es correcta."]

        if errors:
            raise ProfileRejected(errors)

        assert isinstance(sex, str)
        locked.alias = next_alias
        locked.sex = sex
        if changing_password:
            assert isinstance(password, str)
            set_user_password(locked, password)
            # Full save so password-change hooks revoke every prior cookie.
            locked.save()
        else:
            locked.save(update_fields=["alias", "sex"])
        _mirror_alias(locked)
        return ProfileUpdate(locked, password_changed=changing_password)


def _mirror_alias(user: User) -> None:
    """Keep seat rows and living campaign documents in sync with the account alias.

    Campaigns are locked in id order after the user row, matching deactivate_account.
    """
    from apps.campaigns.models import Campaign, Seat
    from hexcampaign.domain.errors import DomainError
    from hexcampaign.domain.game import from_dict, to_dict

    Seat.objects.filter(user=user).update(alias=user.alias)
    campaign_ids = sorted(
        Seat.objects.filter(user=user).values_list("campaign_id", flat=True),
        key=str,
    )
    player_id = str(user.pk)
    for campaign_id in campaign_ids:
        campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
        try:
            game = from_dict(campaign.state)
        except DomainError:
            continue
        changed = False
        for member in game.members:
            if member.player_id == player_id and member.alias != user.alias:
                member.alias = user.alias
                changed = True
        if changed:
            campaign.state = to_dict(game)
            campaign.save(update_fields=["state", "updated_at"])
