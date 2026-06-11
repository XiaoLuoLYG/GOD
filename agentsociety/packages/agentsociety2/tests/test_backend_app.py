from fastapi.testclient import TestClient

from agentsociety2.backend import app as backend_app


def test_cors_allows_local_control_room_origin():
    client = TestClient(backend_app.app)

    response = client.get(
        "/health",
        headers={"Origin": "http://127.0.0.1:5174"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_rejects_unlisted_origin():
    client = TestClient(backend_app.app)

    response = client.get(
        "/health",
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_uses_allowlist():
    client = TestClient(backend_app.app)

    allowed = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    denied = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5174"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_cors_env_override_parser(monkeypatch):
    monkeypatch.setenv("GOD_CORS_ALLOW_ORIGINS", "https://god.example, http://localhost:9999/")

    assert backend_app._cors_allow_origins() == [
        "https://god.example",
        "http://localhost:9999",
    ]
