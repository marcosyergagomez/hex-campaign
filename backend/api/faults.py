"""Log an unhandled error with its request id, then answer with a clean 500.

FastAPI hands an Exception handler to ServerErrorMiddleware, which sits outside
the request-id middleware. The id is therefore read from the scope, where that
middleware stored it, and put back on the log record and the response.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.request_id import HEADER, current_request_id, request_id_var
from apps.campaigns.telemetry import note_unhandled

log = logging.getLogger("hexcampaign.http")

INTERNAL = "Error interno."


def _request_id(request: Request) -> str:
    stored = request.scope.get("hexcampaign.request_id")
    if isinstance(stored, str) and stored:
        return stored
    return current_request_id()


def install(api: FastAPI) -> None:
    @api.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        token = request_id_var.set(request_id)
        try:
            log.error(
                "error no controlado request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
                exc_info=exc,
            )
            note_unhandled(request_id)
        finally:
            request_id_var.reset(token)
        response = JSONResponse(status_code=500, content={"detail": INTERNAL})
        response.headers[HEADER] = request_id
        return response
