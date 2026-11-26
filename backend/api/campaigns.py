"""Campaign HTTP API. The rules live in the domain; this module only adapts them."""

import random

from django.utils import timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from api.django_db import django_sync
from api.player_gate import reader as _reader
from api.player_gate import writer as _writer
from api.player_session import SESSION_MESSAGE
from apps.campaigns.records import (
    CampaignError,
    RevisionConflict,
    accept_alias,
    accept_link,
    campaign_pulse,
    create_campaign,
    inbox,
    decline_invitation,
    invite_alias,
    invite_link,
    list_campaigns,
    list_invitations,
    list_notifications,
    mark_notification_read,
    play,
    present,
    present_fort_delta,
    present_roads_delta,
    preview_link,
    read_campaign,
    resend_invitation,
    revoke_invitation,
    scrap_campaign,
    search_players,
)
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.identity import COLORS, FACTIONS, LEGACY
from hexcampaign.domain.lobby import (
    begin,
    change_rules,
    choose_identity,
    claim_color,
    close_placement,
    confirm_placement,
    describe_army,
    stand_token,
    clear_ready,
    mark_ready,
    place_armies,
)
from hexcampaign.domain.roads import clear_road, finish_roads, place_road
from hexcampaign.domain.rules import Rules, rules_from
from hexcampaign.domain.turn import (
    close_orders,
    expel_player,
    judge_battle,
    leave_campaign,
    lock_orders,
    promote_player,
    report_battle,
    restore_player,
    revert_turn,
)

router = APIRouter()

_MESSAGES = {
    "rules_invalid": "Las reglas no son válidas.",
    "phase_invalid": "Esa acción no corresponde a esta fase.",
    "forbidden": "No puedes hacer eso en esta campaña.",
    "seat_full": "La campaña ya no tiene plazas.",
    "already_joined": "Ya estás en esta campaña.",
    "expelled": "No puedes volver a esta campaña.",
    "order_illegal": "Esa orden no es legal.",
    "text_invalid": "Ese texto no es válido.",
    "battle_closed": "Esa batalla ya está cerrada.",
    "battle_unknown": "Esa batalla no existe.",
    "cannot_expel_owner": "El propietario activo no se puede expulsar.",
    "not_found": "No hay ninguna campaña con ese identificador.",
    "unknown_player": "No hay ningún jugador con ese alias.",
    "invitation_invalid": "La invitación no es válida.",
    "revision_conflict": "La campaña ha cambiado. Vuelve a leerla.",
    "campaign_limit": "Ya tienes tres campañas en curso.",
    "invitee_campaign_limit": "Ese jugador ya tiene tres campañas en curso.",
    "campaign_delete_locked": "Esa campaña no se puede eliminar así.",
    "confirm_name_mismatch": "Escribe el nombre exacto de la campaña para confirmar.",
    "map_unknown": "No hay ningún mapa con ese identificador.",
    "faction_invalid": "Elige una raza de The Old World.",
    "color_invalid": "Elige un color de la paleta.",
    "color_taken": "Ese color ya pertenece a otro jugador.",
    "identity_required": "Todos los jugadores deben elegir raza y color antes de empezar.",
    "lobby_not_ready": "Todos los jugadores deben estar listos antes de iniciar.",
}
_STATUS = {
    "not_found": 404,
    "invitation_invalid": 404,
    "forbidden": 403,
    "map_unknown": 404,
}


class RulesBody(BaseModel):
    seats: int
    armies: int
    movement: int
    map_size: int
    visibility: str
    victory: str
    hold_turns: int
    placement: str
    order_days: int
    battle_days: int
    missed_turns: int
    roster_required: bool = False


class CreateBody(BaseModel):
    name: str
    rules: RulesBody
    description: str = ""
    map_id: str | None = None
    blind: bool = False


class RevisionBody(BaseModel):
    revision: int


class IdentityBody(RevisionBody):
    faction: str
class ReadyBody(RevisionBody):
    ready: bool = True


class IdentityBody(RevisionBody):
    faction: str
    color: str


class ColorBody(RevisionBody):
    color: str


class RulesChange(BaseModel):
    revision: int
    name: str
    rules: RulesBody
    description: str | None = None


class AliasBody(BaseModel):
    revision: int
    alias: str


class StartBody(BaseModel):
    revision: int
    admins: list[str] = Field(default_factory=list)


class HexBody(BaseModel):
    q: int
    r: int


class PlaceBody(BaseModel):
    revision: int
    fortress: HexBody
    armies: dict[str, HexBody]


class RoadBody(BaseModel):
    revision: int
    q: int
    r: int


class ArmyBody(BaseModel):
    revision: int
    name: str
    commander: str = ""
    race: str = ""
    roster: str = ""


class OrdersBody(BaseModel):
    revision: int
    orders: dict[str, list[HexBody]]


class BattleBody(BaseModel):
    revision: int
    result: str


class PlayerBody(BaseModel):
    revision: int
    player_id: str


class ScrapBody(BaseModel):
    confirm_name: str


def _errors(status: int, field: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"errors": {field: [message]}})


def _failure(exc: CampaignError) -> JSONResponse:
    if exc.code == "account_inactive":
        return _errors(401, "session", SESSION_MESSAGE)
    if exc.code == "revision_conflict":
        return _errors(409, "revision", _MESSAGES["revision_conflict"])
    status = _STATUS.get(exc.code, 422)
    message = _MESSAGES.get(exc.code, _MESSAGES["rules_invalid"])
    return _errors(status, "campaign", message)


def _run(request: Request, action):
    user = _writer(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return action(user)
    except RevisionConflict as exc:
        return _failure(exc)
    except CampaignError as exc:
        return _failure(exc)


def _view(user, campaign, game, status: int = 200) -> JSONResponse:
    return JSONResponse(present(campaign, game, user, timezone.now()), status_code=status)


def _play(user, campaign_id: str, revision: int, command) -> JSONResponse:
    return _view(user, *play(user, campaign_id, revision, command))


def _road_play(user, campaign_id: str, revision: int, command, changed: list[Hex]) -> JSONResponse:
    """Preparing stays on a delta; leaving preparation returns the full table view."""
    campaign, game = play(user, campaign_id, revision, command)
    # Finishing roads moves this seat on to its armies, so the token list has to come back whole.
    if game.phase != "preparing" or not changed:
        return _view(user, campaign, game)
    return JSONResponse(present_roads_delta(campaign, game, user, changed))


def _hexes(steps: list[HexBody]) -> list[Hex]:
    return [Hex(step.q, step.r) for step in steps]


def _rules(body: RulesBody) -> Rules:
    try:
        return rules_from(body.model_dump())
    except DomainError as exc:
        raise CampaignError(exc.code) from exc


@router.get("/api/campaigns")
@django_sync
def get_campaigns(request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    return JSONResponse(list_campaigns(user))


@router.get("/api/campaign-identity")
@django_sync
def get_identity_options(request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    return JSONResponse({
        "factions": [{"id": faction, "legacy": faction in LEGACY} for faction in FACTIONS],
        "colors": [{"id": name, "value": color} for name, color in COLORS.items()],
    })


@router.post("/api/campaigns/{campaign_id}/identity")
@django_sync
def post_identity(campaign_id: str, payload: IdentityBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return choose_identity(game, str(user.pk), payload.faction, payload.color)

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/color")
@django_sync
def post_color(campaign_id: str, payload: ColorBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return claim_color(game, str(user.pk), payload.color)

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/ready")
@django_sync
def post_ready(campaign_id: str, payload: ReadyBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            if payload.ready:
                return mark_ready(game, str(user.pk))
            return clear_ready(game, str(user.pk))

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns", status_code=201)
@django_sync
def post_campaign(payload: CreateBody, request: Request) -> JSONResponse:
    def action(user):
        template = None
        if payload.map_id:
            from apps.campaigns.atlases import take_template

            template = take_template(user, payload.map_id)
        campaign, game = create_campaign(
            user,
            payload.name,
            payload.rules.model_dump(),
            template,
            payload.blind,
            payload.description,
        )
        return _view(user, campaign, game, 201)

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/scrap", response_model=None)
@django_sync
def post_scrap_campaign(campaign_id: str, payload: ScrapBody, request: Request):
    """Leave or destroy a campaign after the player types its name."""

    def action(user):
        scrap_campaign(user, campaign_id, payload.confirm_name)
        return Response(status_code=204)

    return _run(request, action)


@router.get("/api/campaigns/{campaign_id}")
@django_sync
def get_campaign(campaign_id: str, request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return JSONResponse(read_campaign(user, campaign_id, timezone.now()))
    except CampaignError as exc:
        return _failure(exc)


@router.get("/api/campaigns/{campaign_id}/pulse")
@django_sync
def get_campaign_pulse(campaign_id: str, request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return JSONResponse(campaign_pulse(user, campaign_id))
    except CampaignError as exc:
        return _failure(exc)


@router.get("/api/invitations")
@django_sync
def get_invitations(request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    return JSONResponse(inbox(user))


@router.get("/api/players")
@django_sync
def get_players(request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    query = request.query_params.get("q", "")
    return JSONResponse(search_players(user, query))


@router.get("/api/notifications")
@django_sync
def get_notifications(request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    return JSONResponse(list_notifications(user))


@router.post("/api/notifications/{notification_id}/read")
@django_sync
def post_notification_read(notification_id: str, request: Request) -> JSONResponse:
    def action(user):
        return JSONResponse(mark_notification_read(user, notification_id))

    return _run(request, action)


@router.get("/api/invitations/{token}")
@django_sync
def get_invitation(token: str, request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return JSONResponse(preview_link(user, token))
    except CampaignError as exc:
        return _failure(exc)


@router.post("/api/campaigns/{campaign_id}/rules")
@django_sync
def post_rules(campaign_id: str, payload: RulesChange, request: Request) -> JSONResponse:
    def action(user):
        rules = _rules(payload.rules)

        def command(game):
            return change_rules(game, str(user.pk), payload.name, rules, payload.description)

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/invitations")
@django_sync
def post_invitation(campaign_id: str, payload: AliasBody, request: Request) -> JSONResponse:
    def action(user):
        saved = invite_alias(user, campaign_id, payload.revision, payload.alias)
        return _view(user, *saved)

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/links", status_code=201)
@django_sync
@router.get("/api/campaigns/{campaign_id}/invitations")
@django_sync
def get_campaign_invitations(campaign_id: str, request: Request) -> JSONResponse:
    user = _reader(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return JSONResponse(list_invitations(user, campaign_id))
    except CampaignError as exc:
        return _failure(exc)


@router.post("/api/campaigns/{campaign_id}/invitations/{invitation_id}/revoke")
@django_sync
def post_revoke_invitation(campaign_id: str, invitation_id: str, request: Request) -> Response:
    def action(user):
        revoke_invitation(user, campaign_id, invitation_id)
        return Response(status_code=204)

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/invitations/{invitation_id}/resend")
@django_sync
def post_resend_invitation(campaign_id: str, invitation_id: str, request: Request) -> Response:
    def action(user):
        resend_invitation(user, campaign_id, invitation_id)
        return Response(status_code=204)

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/invitations/decline")
@django_sync
def post_decline_invitation(campaign_id: str, request: Request) -> Response:
    def action(user):
        decline_invitation(user, campaign_id)
        return Response(status_code=204)

    return _run(request, action)


def post_link(campaign_id: str, request: Request) -> JSONResponse:
    def action(user):
        return JSONResponse({"token": invite_link(user, campaign_id)}, status_code=201)

    return _run(request, action)


@router.post("/api/invitations/{token}/accept")
@django_sync
def post_accept(token: str, payload: RevisionBody, request: Request) -> JSONResponse:
    def action(user):
        return _view(user, *accept_link(user, token, payload.revision))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/join")
@django_sync
def post_join(campaign_id: str, payload: RevisionBody, request: Request) -> JSONResponse:
    def action(user):
        return _view(user, *accept_alias(user, campaign_id, payload.revision))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/start")
@django_sync
def post_start(campaign_id: str, payload: StartBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return begin(game, str(user.pk), payload.admins, timezone.now())

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/placement/ready")
@django_sync
def post_placement_ready(campaign_id: str, payload: RevisionBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return confirm_placement(game, str(user.pk), timezone.now())

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/placement")
@django_sync
def post_placement(campaign_id: str, payload: PlaceBody, request: Request) -> JSONResponse:
    def action(user):
        spots = {army_id: Hex(spot.q, spot.r) for army_id, spot in payload.armies.items()}

        def command(game):
            fortress = Hex(payload.fortress.q, payload.fortress.r)
            return place_armies(game, str(user.pk), fortress, spots)

        campaign, game = play(user, campaign_id, payload.revision, command)
        return JSONResponse(present_fort_delta(campaign, game, user))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/placement/close")
@django_sync
def post_close_placement(campaign_id: str, payload: RevisionBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return close_placement(game, str(user.pk), timezone.now())

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/roads")
@django_sync
def post_road(campaign_id: str, payload: RoadBody, request: Request) -> JSONResponse:
    cell = Hex(payload.q, payload.r)

    def action(user):
        return _road_play(
            user,
            campaign_id,
            payload.revision,
            lambda game: place_road(game, str(user.pk), cell),
            [cell],
        )

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/roads/clear")
@django_sync
def post_clear_road(campaign_id: str, payload: RoadBody, request: Request) -> JSONResponse:
    cell = Hex(payload.q, payload.r)

    def action(user):
        return _road_play(
            user,
            campaign_id,
            payload.revision,
            lambda game: clear_road(game, str(user.pk), cell),
            [cell],
        )

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/roads/ready")
@django_sync
def post_roads_ready(campaign_id: str, payload: RevisionBody, request: Request) -> JSONResponse:
    def action(user):
        return _road_play(
            user,
            campaign_id,
            payload.revision,
            lambda game: finish_roads(game, str(user.pk), timezone.now()),
            [],
        )

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/armies/{army_id}/stand")
@django_sync
def post_stand(campaign_id: str, army_id: str, payload: RoadBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return stand_token(game, str(user.pk), army_id, Hex(payload.q, payload.r), timezone.now())

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/armies/{army_id}")
@django_sync
def post_army(campaign_id: str, army_id: str, payload: ArmyBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return describe_army(
                game,
                str(user.pk),
                army_id,
                payload.name,
                payload.commander,
                payload.race,
                payload.roster,
            )

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/orders")
@django_sync
def post_orders(campaign_id: str, payload: OrdersBody, request: Request) -> JSONResponse:
    def action(user):
        paths = {army_id: _hexes(steps) for army_id, steps in payload.orders.items()}

        def command(game):
            return lock_orders(game, str(user.pk), paths, timezone.now())

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/orders/close")
@django_sync
def post_close_orders(campaign_id: str, payload: RevisionBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return close_orders(game, str(user.pk), timezone.now())

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/battles/{battle_id}")
@django_sync
def post_battle(
    campaign_id: str,
    battle_id: str,
    payload: BattleBody,
    request: Request,
) -> JSONResponse:
    def action(user):
        def command(game):
            return report_battle(game, str(user.pk), battle_id, payload.result, timezone.now())

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/battles/{battle_id}/judge")
@django_sync
def post_judge(
    campaign_id: str,
    battle_id: str,
    payload: BattleBody,
    request: Request,
) -> JSONResponse:
    def action(user):
        def command(game):
            return judge_battle(game, str(user.pk), battle_id, payload.result, timezone.now())

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/expel")
@django_sync
def post_expel(campaign_id: str, payload: PlayerBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return expel_player(
                game,
                str(user.pk),
                payload.player_id,
                random.Random(),
                timezone.now(),
            )

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/leave")
@django_sync
def post_leave(campaign_id: str, payload: RevisionBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return leave_campaign(game, str(user.pk), random.Random(), timezone.now())

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/admins")
@django_sync
def post_admin(campaign_id: str, payload: PlayerBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return promote_player(game, str(user.pk), payload.player_id)

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/restore")
@django_sync
def post_restore(campaign_id: str, payload: PlayerBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return restore_player(game, str(user.pk), payload.player_id)

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/revert")
@django_sync
def post_revert(campaign_id: str, payload: RevisionBody, request: Request) -> JSONResponse:
    def action(user):
        def command(game):
            return revert_turn(game, str(user.pk))

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)
