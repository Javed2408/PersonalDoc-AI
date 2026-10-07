from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    settings = get_settings()
    assert body == {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


def test_health_allows_frontend_origin():
    origin = "http://localhost:5173"
    response = client.get("/api/health", headers={"Origin": origin})

    assert response.headers.get("access-control-allow-origin") == origin


def test_unknown_route_returns_404():
    assert client.get("/api/does-not-exist").status_code == 404
