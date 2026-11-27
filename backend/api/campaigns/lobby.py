"""Create a campaign, read it, and settle the lobby before the march."""

from django.utils import timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from api.campaigns.bodies import (
    ColorBody,
    CreateBody,
    IdentityBody,
    ReadyBody,
    RulesChange,
    ScrapBody,
)
from api.campaigns.http import _failure, _rules, _run, _view
from api.django_db import django_sync
from api.player_gate import reader as _reader
from apps.accounts.models import User
from apps.campaigns.errors import CampaignError
from apps.campaigns.match import create_campaign, play, read_campaign, scrap_campaign
from apps.campaigns.queries import campaign_pulse, list_campaigns
from hexcampaign.domain.game import Game
from hexcampaign.domain.identity import COLORS, FACTIONS, LEGACY
from hexcampaign.domain.lobby import (
    change_rules,
    choose_identity,
    claim_color,
    clear_ready,
    mark_ready,
)

router = APIRouter()


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
    return JSONResponse(
        {
            "factions": [{"id": faction, "legacy": faction in LEGACY} for faction in FACTIONS],
            "colors": [{"id": name, "value": color} for name, color in COLORS.items()],
        }
    )


@router.post("/api/campaigns/{campaign_id}/identity")
@django_sync
def post_identity(campaign_id: str, payload: IdentityBody, request: Request) -> Response:
    def action(user: User) -> Response:
        def command(game: Game) -> Game:
            return choose_identity(game, str(user.pk), payload.faction, payload.color)

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/color")
@django_sync
def post_color(campaign_id: str, payload: ColorBody, request: Request) -> Response:
    def action(user: User) -> Response:
        def command(game: Game) -> Game:
            return claim_color(game, str(user.pk), payload.color)

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns/{campaign_id}/ready")
@django_sync
def post_ready(campaign_id: str, payload: ReadyBody, request: Request) -> Response:
    def action(user: User) -> Response:
        def command(game: Game) -> Game:
            if payload.ready:
                return mark_ready(game, str(user.pk))
            return clear_ready(game, str(user.pk))

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)


@router.post("/api/campaigns", status_code=201)
@django_sync
def post_campaign(payload: CreateBody, request: Request) -> Response:
    def action(user: User) -> Response:
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
def post_scrap_campaign(campaign_id: str, payload: ScrapBody, request: Request) -> Response:
    """Leave or destroy a campaign after the player types its name."""

    def action(user: User) -> Response:
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


@router.post("/api/campaigns/{campaign_id}/rules")
@django_sync
def post_rules(campaign_id: str, payload: RulesChange, request: Request) -> Response:
    def action(user: User) -> Response:
        rules = _rules(payload.rules)

        def command(game: Game) -> Game:
            return change_rules(game, str(user.pk), payload.name, rules, payload.description)

        return _view(user, *play(user, campaign_id, payload.revision, command))

    return _run(request, action)
