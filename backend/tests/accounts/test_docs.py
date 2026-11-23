"""Swagger is available in debug and absent otherwise."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app import api
from api.guard import AccountGuard
from config.asgi import application


def test_schema_is_hidden_when_debug_is_off() -> None:
    assert api.docs_url is None
    assert api.openapi_url is None


@pytest.mark.django_db(transaction=True)
def test_docs_route_is_absent_from_the_test_server() -> None:
    with TestClient(application) as client:
        response = client.get("/api/docs")

    assert response.status_code == 404


def test_swagger_page_loads_when_debug_routes_are_enabled() -> None:
    app = FastAPI(
        title="Hex Campaign",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(AccountGuard)

    with TestClient(app) as client:
        page = client.get("/api/docs")
        spec = client.get("/api/openapi.json")

    assert page.status_code == 200
    assert "swagger-ui" in page.text
    assert "content-security-policy" not in page.headers
    assert spec.status_code == 200
    assert spec.json()["info"]["title"] == "Hex Campaign"
