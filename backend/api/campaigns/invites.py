"""Invitations, player search, and in-app notices."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from api.campaigns.bodies import AliasBody, RevisionBody
from api.campaigns.http import _MESSAGES, _errors, _failure, _run, _view
from api.django_db import django_sync
from api.player_gate import reader as _reader
from apps.campaigns.errors import CampaignError
from apps.campaigns.invitations import (
    accept_alias,
    accept_link,
    decline_invitation,
    invite_alias,
    invite_link,
    list_invitations,
    preview_link,
    resend_invitation,
    revoke_invitation,
    search_players,
)
from apps.campaigns.notices import list_notifications, mark_notification_read
from apps.campaigns.queries import inbox

router = APIRouter()


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
    try:
        found = search_players(user, query)
    except CampaignError as exc:
        if exc.code == "search_limited":
            return _errors(429, "alias", _MESSAGES["search_limited"])
        return _failure(exc)
    return JSONResponse(found)


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


@router.post("/api/campaigns/{campaign_id}/invitations")
@django_sync
def post_invitation(campaign_id: str, payload: AliasBody, request: Request) -> JSONResponse:
    def action(user):
        saved = invite_alias(user, campaign_id, payload.revision, payload.alias)
        return _view(user, *saved)

    return _run(request, action)


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


@router.post("/api/campaigns/{campaign_id}/links", status_code=201)
@django_sync
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
