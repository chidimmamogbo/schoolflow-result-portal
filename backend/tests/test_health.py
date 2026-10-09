"""Tests for the liveness check, GET /api/v1/health (decision D-126).

The health check is public and called often (by Vercel, CI and us after a
deploy), so it must answer without touching the database and must not reveal
anything about the server beyond "I am up".
"""

from fastapi.testclient import TestClient

from schoolflow_api.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_rejects_post() -> None:
    # Only GET is allowed; anything that tries to change state is refused.
    response = client.post("/api/v1/health")

    assert response.status_code == 405
