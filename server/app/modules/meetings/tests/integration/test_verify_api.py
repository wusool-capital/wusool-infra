"""GET /desktop/verify — no DB involved, so this runs as a plain unit test
against a bare app built from just the verify router, matching
`ddl_commands/tests/unit/test_attio_sync_router.py`'s pattern. Lives under
`tests/integration/` anyway per `meetings/tests/`'s existing (empty)
layout, since `checks.sh integration()` is what currently runs this
module's api tests.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.meetings.api.verify import router as verify_router
from app.modules.meetings.config import get_settings
from app.modules.utilities.api.handlers import register_exception_handlers

_VALID_KEY = "test-desktop-api-key"  # matches conftest.py's DESKTOP_API_KEY default


def _make_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(verify_router)
    return TestClient(app)


def test_valid_key_returns_ok() -> None:
    assert get_settings().desktop_api_key == _VALID_KEY

    response = _make_client().get(
        "/desktop/verify", headers={"Authorization": f"Bearer {_VALID_KEY}"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_wrong_key_is_rejected() -> None:
    response = _make_client().get(
        "/desktop/verify", headers={"Authorization": "Bearer wrong-key"}
    )

    assert response.status_code == 401


def test_missing_authorization_header_is_rejected() -> None:
    response = _make_client().get("/desktop/verify")

    assert response.status_code == 401
