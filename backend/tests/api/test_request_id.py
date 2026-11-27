"""Each API response carries X-Request-ID, and logs stamped during the request do too."""

import logging

import pytest
from fastapi.testclient import TestClient

from api.request_id import RequestIdFilter, RequestIdFormatter
from config.asgi import application


@pytest.mark.django_db(transaction=True)
def test_response_returns_request_id_and_logs_include_it() -> None:
    logger = logging.getLogger("hexcampaign.http")
    captured: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.setLevel(logging.DEBUG)
    handler.addFilter(RequestIdFilter())
    handler.emit = captured.append  # type: ignore[method-assign]
    previous = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        with TestClient(application) as client:
            echoed = client.get("/api/session", headers={"x-request-id": "trace-42"})
            minted = client.get("/api/session", headers={"x-request-id": "bad id\n"})
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)

    assert echoed.headers["x-request-id"] == "trace-42"
    assert echoed.status_code == 401
    minted_id = minted.headers["x-request-id"]
    assert minted_id != "bad id\n"
    assert minted_id != "trace-42"

    own = [record for record in captured if getattr(record, "request_id", None) == "trace-42"]
    assert own
    rendered = RequestIdFormatter().format(own[0])
    assert "request_id=trace-42" in rendered
