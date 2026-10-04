"""DELETE /desktop/meetings/{install_id}/{local_recording_id} — auth plus
the 204/409 response shapes. The service itself is faked via
`dependency_overrides`, matching how DB-free desktop routes are tested here
(see `test_verify_api.py`); `test_delete.py` covers `DeleteMixin`'s own
behaviour against fakes.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.meetings.api.delete import router as delete_router
from app.modules.meetings.api.dependencies import get_meetings_service
from app.modules.meetings.application.errors import MeetingStillProcessingError
from app.modules.utilities.api.handlers import register_exception_handlers

_VALID_KEY = "test-desktop-api-key"  # matches conftest.py's DESKTOP_API_KEY default


class _FakeService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def delete_meeting(self, install_id: str, local_recording_id: str) -> None:
        self.calls.append((install_id, local_recording_id))
        if self.error is not None:
            raise self.error


def _make_client(service: _FakeService) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(delete_router)
    app.dependency_overrides[get_meetings_service] = lambda: service
    return TestClient(app)


def test_delete_returns_204_on_success() -> None:
    service = _FakeService()

    response = _make_client(service).delete(
        "/desktop/meetings/install-1/rec-1", headers={"Authorization": f"Bearer {_VALID_KEY}"}
    )

    assert response.status_code == 204
    assert service.calls == [("install-1", "rec-1")]


def test_delete_returns_409_when_still_summarizing() -> None:
    service = _FakeService(error=MeetingStillProcessingError("still summarizing"))

    response = _make_client(service).delete(
        "/desktop/meetings/install-1/rec-1", headers={"Authorization": f"Bearer {_VALID_KEY}"}
    )

    assert response.status_code == 409


def test_delete_without_key_is_rejected() -> None:
    response = _make_client(_FakeService()).delete("/desktop/meetings/install-1/rec-1")

    assert response.status_code == 401
