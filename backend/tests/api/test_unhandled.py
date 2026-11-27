"""An unhandled exception becomes a clean 500 and a log line that carries the request id."""

import logging

import pytest
from fastapi.testclient import TestClient

from api.app import api
from api.faults import INTERNAL
from api.request_id import RequestIdFilter, RequestIdFormatter
from config.asgi import application


@pytest.mark.django_db(transaction=True)
def test_unhandled_exception_returns_clean_500_and_logs_the_request_id() -> None:
    def explode() -> None:
        raise RuntimeError("boom-secret")

    api.add_api_route("/api/_boom", explode, methods=["GET"])
    logger = logging.getLogger("hexcampaign.http")
    captured: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.setLevel(logging.ERROR)
    handler.addFilter(RequestIdFilter())
    handler.emit = captured.append  # type: ignore[method-assign]
    previous = logger.level
    logger.setLevel(logging.ERROR)
    logger.addHandler(handler)
    try:
        with TestClient(application, raise_server_exceptions=False) as client:
            failed = client.get("/api/_boom", headers={"x-request-id": "trace-500"})
            refused = client.get("/api/session", headers={"x-request-id": "trace-401"})
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)
        api.router.routes[:] = [
            route
            for route in api.router.routes
            if getattr(route, "path", None) != "/api/_boom"
        ]

    assert failed.status_code == 500
    assert failed.json() == {"detail": INTERNAL}
    assert "boom-secret" not in failed.text
    assert failed.headers["x-request-id"] == "trace-500"
    assert refused.status_code == 401

    own = [record for record in captured if "trace-500" in record.getMessage()]
    assert own
    assert own[0].exc_info is not None
    assert own[0].exc_info[0] is RuntimeError
    rendered = RequestIdFormatter().format(own[0])
    assert "request_id=trace-500" in rendered
    assert "RuntimeError" in rendered
    assert "boom-secret" in rendered
