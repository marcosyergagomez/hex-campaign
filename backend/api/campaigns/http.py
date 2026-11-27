"""Shared HTTP translation for campaign routes."""

from collections.abc import Callable

from django.utils import timezone
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from api.campaigns.bodies import HexBody, RulesBody
from api.player_gate import writer as _writer
from api.player_session import SESSION_MESSAGE
from apps.accounts.models import User
from apps.campaigns.errors import CampaignError, RevisionConflict
from apps.campaigns.match import play, present, present_roads_delta
from apps.campaigns.models import Campaign
from apps.campaigns.telemetry import note_revision_conflict
from hexcampaign.domain.errors import DomainError
from hexcampaign.domain.game import Game
from hexcampaign.domain.hexes import Hex
from hexcampaign.domain.rules import Rules, rules_from

_MESSAGES = {
    "rules_invalid": "Las reglas no son válidas.",
    "phase_invalid": "Esa acción no corresponde a esta fase.",
    "forbidden": "No puedes hacer eso en esta campaña.",
    "seat_full": "La campaña ya no tiene plazas.",
    "already_joined": "Ya estás en esta campaña.",
    "expelled": "No puedes volver a esta campaña.",
    "order_illegal": "Esa orden no es legal.",
    "text_invalid": "Ese texto no es válido.",
    "sheet_incomplete": "Falta el comandante o la lista obligatoria de un ejército.",
    "commander_taken": "Ese comandante ya está en otro ejército tuyo.",
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
    "search_limited": "Demasiadas búsquedas. Prueba de nuevo en unos minutos.",
}
_STATUS = {
    "not_found": 404,
    "invitation_invalid": 404,
    "forbidden": 403,
    "map_unknown": 404,
}


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


def _run(request: Request, action: Callable[[User], Response]) -> Response:
    user = _writer(request)
    if isinstance(user, JSONResponse):
        return user
    try:
        return action(user)
    except RevisionConflict as exc:
        note_revision_conflict()
        return _failure(exc)
    except CampaignError as exc:
        return _failure(exc)


def _view(user: User, campaign: Campaign, game: Game, status: int = 200) -> JSONResponse:
    return JSONResponse(present(campaign, game, user, timezone.now()), status_code=status)


def _road_play(
    user: User,
    campaign_id: str,
    revision: int,
    command: Callable[[Game], Game],
    changed: list[Hex],
) -> JSONResponse:
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
