import pytest

from app.config import get_settings


def test_health_returns_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    settings = get_settings()
    assert body == {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "llm": {"status": "ready", "model": "test/fake-llm"},
    }


@pytest.mark.parametrize("llm_status", ["unavailable", "model_missing"])
def test_health_reports_the_local_llm_separately_from_the_backend(client, llm, llm_status):
    llm.health = llm_status

    body = client.get("/api/health").json()

    assert body["status"] == "ok"  # The backend is still up
    assert body["llm"] == {"status": llm_status, "model": "test/fake-llm"}


def test_health_does_not_expose_the_ollama_address(client):
    assert "11434" not in client.get("/api/health").text


def test_health_allows_frontend_origin(client):
    origin = "http://localhost:5173"
    response = client.get("/api/health", headers={"Origin": origin})

    assert response.headers.get("access-control-allow-origin") == origin


def test_unknown_route_returns_404(client):
    assert client.get("/api/does-not-exist").status_code == 404
