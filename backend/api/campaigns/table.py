"""Orders, preparation, battles, and staff actions on a live table."""

import random

from django.utils import timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.campaigns.bodies import (
    ArmyBody,
    BattleBody,
    OrdersBody,
    PlaceBody,
    PlayerBody,
    RevisionBody,
    RoadBody,
    StartBody,
)
from api.campaigns.http import _hexes, _road_play, _run, _view
from api.django_db import django_sync
from apps.campaigns.match import play, present_fort_delta
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.lobby import (
    begin,
    close_placement,
    confirm_placement,
    describe_army,
    place_armies,
    stand_token,
)
from hexcampaign.domain.roads import clear_road, finish_roads, place_road
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
            return stand_token(
                game,
                str(user.pk),
                army_id,
                Hex(payload.q, payload.r),
                timezone.now(),
            )

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
