"""PUT /desktop/meetings/{install_id}/{local_recording_id}/user-notes — auth,
validation and the 204/404 response shapes. The service is faked via
`dependency_overrides`, as in `test_delete_api.py`; `test_user_notes.py`
covers `UserNotesMixin` itself.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.meetings.api.dependencies import get_meetings_service
from app.modules.meetings.api.schemas import USER_NOTES_MAX_CHARS
from app.modules.meetings.api.user_notes import router as user_notes_router
from app.modules.meetings.application.errors import MeetingNotFoundError
from app.modules.utilities.api.handlers import register_exception_handlers

_VALID_KEY = "test-desktop-api-key"  # matches conftest.py's DESKTOP_API_KEY default
_URL = "/desktop/meetings/install-1/rec-1/user-notes"
_AUTH = {"Authorization": f"Bearer {_VALID_KEY}"}


class _FakeService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str, str | None]] = []

    async def update_user_notes(
        self, install_id: str, local_recording_id: str, user_notes: str | None
    ) -> None:
        self.calls.append((install_id, local_recording_id, user_notes))
        if self.error is not None:
            raise self.error


def _make_client(service: _FakeService) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(user_notes_router)
    app.dependency_overrides[get_meetings_service] = lambda: service
    return TestClient(app)


def test_put_returns_204_on_success() -> None:
    service = _FakeService()

    response = _make_client(service).put(_URL, json={"user_notes": "- SOC2"}, headers=_AUTH)

    assert response.status_code == 204
    assert service.calls == [("install-1", "rec-1", "- SOC2")]


def test_put_returns_404_when_meeting_is_gone() -> None:
    service = _FakeService(error=MeetingNotFoundError("gone"))

    response = _make_client(service).put(_URL, json={"user_notes": "x"}, headers=_AUTH)

    assert response.status_code == 404


def test_put_rejects_oversized_notes() -> None:
    service = _FakeService()

    response = _make_client(service).put(
        _URL, json={"user_notes": "x" * (USER_NOTES_MAX_CHARS + 1)}, headers=_AUTH
    )

    assert response.status_code == 422
    assert service.calls == []


def test_put_without_key_is_rejected() -> None:
    response = _make_client(_FakeService()).put(_URL, json={"user_notes": "x"})

    assert response.status_code == 401
