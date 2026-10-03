"""POST /desktop/transcripts/corrections — auth and wire schema. The service
is faked via `dependency_overrides`, like the other DB-free desktop routes."""

from collections.abc import Sequence

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.meetings.api.corrections import router as corrections_router
from app.modules.meetings.api.dependencies import get_correction_service
from app.modules.meetings.application.corrections import CorrectionService
from app.modules.meetings.domain.corrections import CorrectionSuggestion, TranscriptSegment
from app.modules.utilities.api.handlers import register_exception_handlers

_VALID_KEY = "test-desktop-api-key"  # matches conftest.py's DESKTOP_API_KEY default
_URL = "/desktop/transcripts/corrections"


class _FakeService:
    def __init__(self) -> None:
        self.received: list[TranscriptSegment] = []

    async def suggest(self, segments: Sequence[TranscriptSegment]) -> list[CorrectionSuggestion]:
        self.received = list(segments)
        return [
            CorrectionSuggestion(
                segment_id="s1", original="wusul", suggested="Wusool", reason="company name"
            )
        ]


def _make_client(service: _FakeService) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(corrections_router)

    def fake() -> CorrectionService:
        return service  # ty: ignore[invalid-return-type]

    app.dependency_overrides[get_correction_service] = fake
    return TestClient(app)


def test_requires_api_key() -> None:
    response = _make_client(_FakeService()).post(_URL, json={"segments": []})

    assert response.status_code == 401


def test_returns_suggestions() -> None:
    service = _FakeService()

    response = _make_client(service).post(
        _URL,
        json={"segments": [{"segment_id": "s1", "text": "wusul"}]},
        headers={"Authorization": f"Bearer {_VALID_KEY}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "suggestions": [
            {
                "segment_id": "s1",
                "original": "wusul",
                "suggested": "Wusool",
                "reason": "company name",
            }
        ]
    }
    assert service.received == [TranscriptSegment("s1", "wusul")]


def test_rejects_malformed_body() -> None:
    response = _make_client(_FakeService()).post(
        _URL,
        json={"segments": [{"text": "no id"}]},
        headers={"Authorization": f"Bearer {_VALID_KEY}"},
    )

    assert response.status_code == 422
