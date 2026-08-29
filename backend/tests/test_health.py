from fastapi.testclient import TestClient

from app.db.session import get_database
from app.main import app

client = TestClient(app)


def test_health_matches_frozen_contract() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "kalasetu-api",
        "version": "0.1.0",
        "environment": "test",
    }


def test_swagger_is_available_at_documented_url() -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text


def test_flutter_web_origin_is_allowed() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_health_reports_degraded_when_database_is_unavailable() -> None:
    class UnavailableDatabase:
        @staticmethod
        def is_available() -> bool:
            return False

    app.dependency_overrides[get_database] = UnavailableDatabase
    try:
        response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides.pop(get_database, None)

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
