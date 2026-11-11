"""POST /desktop/transcripts/corrections — auth and wire schema. The service
is faked via `dependency_overrides`, like the other DB-free desktop routes."""

from collections.abc import Sequence

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.meetings.api.corrections import router as corrections_router
from app.modules.meetings.api.dependencies import get_correction_service
from app.modules.meetings.application.corrections import CorrectionService
from app.modules.meetings.domain.corrections import (
    CorrectionContext,
    CorrectionResult,
    CorrectionSuggestion,
    TranscriptSegment,
)
from app.modules.utilities.api.handlers import register_exception_handlers

_VALID_KEY = "test-desktop-api-key"  # matches conftest.py's DESKTOP_API_KEY default
_URL = "/desktop/transcripts/corrections"


class _FakeService:
    def __init__(self) -> None:
        self.received: list[TranscriptSegment] = []
        self.context: CorrectionContext | None = None

    async def suggest(
        self, segments: Sequence[TranscriptSegment], context: CorrectionContext | None = None
    ) -> CorrectionResult:
        self.received = list(segments)
        self.context = context
        return CorrectionResult(
            suggestions=[
                CorrectionSuggestion(
                    segment_id="s1",
                    original="wusul",
                    suggested="Wusool",
                    category="name",
                    reason="company name",
                )
            ],
            checked_segments=1,
        )


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
                "category": "name",
                "reason": "company name",
            }
        ],
        "checked_segments": 1,
        "failed_segment_ids": [],
    }
    assert service.received == [TranscriptSegment("s1", "wusul")]
    assert service.context is None


def test_passes_speakers_and_context_through() -> None:
    service = _FakeService()

    response = _make_client(service).post(
        _URL,
        json={
            "segments": [{"segment_id": "s1", "text": "wusul", "speaker": "Khalid"}],
            "context": {"title": "Floor call", "names": ["Al Waha"], "vocabulary": ["Falcon"]},
        },
        headers={"Authorization": f"Bearer {_VALID_KEY}"},
    )

    assert response.status_code == 200
    assert service.received == [TranscriptSegment("s1", "wusul", speaker="Khalid")]
    assert service.context == CorrectionContext(
        title="Floor call", names=("Al Waha",), vocabulary=("Falcon",)
    )


def test_rejects_oversized_context() -> None:
    response = _make_client(_FakeService()).post(
        _URL,
        json={
            "segments": [{"segment_id": "s1", "text": "a"}],
            "context": {"vocabulary": ["w"] * 201},
        },
        headers={"Authorization": f"Bearer {_VALID_KEY}"},
    )

    assert response.status_code == 422


def test_rejects_malformed_body() -> None:
    response = _make_client(_FakeService()).post(
        _URL,
        json={"segments": [{"text": "no id"}]},
        headers={"Authorization": f"Bearer {_VALID_KEY}"},
    )

    assert response.status_code == 422


def test_rejects_duplicate_segment_ids() -> None:
    response = _make_client(_FakeService()).post(
        _URL,
        json={"segments": [{"segment_id": "s1", "text": "a"}, {"segment_id": "s1", "text": "b"}]},
        headers={"Authorization": f"Bearer {_VALID_KEY}"},
    )

    assert response.status_code == 422


def test_rejects_oversized_transcript() -> None:
    response = _make_client(_FakeService()).post(
        _URL,
        json={"segments": [{"segment_id": "s1", "text": "x" * 200_001}]},
        headers={"Authorization": f"Bearer {_VALID_KEY}"},
    )

    assert response.status_code == 422
