from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import __version__
from app.core.config import Settings
from app.main import create_app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "Test API"
    assert body["version"] == __version__
    assert body["environment"] == "testing"
    # Timestamp must be a timezone-aware ISO-8601 value.
    assert datetime.fromisoformat(body["timestamp"]).tzinfo is not None


def test_health_uses_injected_settings() -> None:
    custom = Settings(_env_file=None, app_name="Other Name", environment="production")
    body = TestClient(create_app(custom)).get("/health").json()
    assert body["service"] == "Other Name"
    assert body["environment"] == "production"


def test_health_rejects_non_get(client: TestClient) -> None:
    assert client.post("/health").status_code == 405


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/does-not-exist").status_code == 404


def test_openapi_and_docs_available(client: TestClient) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/health" in schema.json()["paths"]
    assert "not" in schema.json()["info"]["description"].lower()  # disclaimer present
    assert client.get("/docs").status_code == 200


def test_response_gets_generated_request_id(client: TestClient) -> None:
    first = client.get("/health").headers["x-request-id"]
    second = client.get("/health").headers["x-request-id"]
    assert first and second and first != second


def test_valid_client_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-123.abc"})
    assert response.headers["x-request-id"] == "trace-123.abc"


def test_malformed_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "bad id with spaces!"})
    assert response.headers["x-request-id"] != "bad id with spaces!"
    assert len(response.headers["x-request-id"]) == 32


def test_unhandled_exception_returns_generic_500(settings: Settings) -> None:
    app: FastAPI = create_app(settings)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret patient detail")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret" not in response.text
