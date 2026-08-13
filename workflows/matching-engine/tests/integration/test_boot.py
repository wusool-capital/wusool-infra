"""Architecture/boot tests: the app imports and starts without a live database.

`/readiness` is expected to return 503 in this environment (no DB tunnel) —
that's the correct behavior, not a failure to fix.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_app_imports() -> None:
    assert app is not None


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_responds_without_live_database() -> None:
    client = TestClient(app)
    response = client.get("/readiness")
    assert response.status_code in (200, 503)
