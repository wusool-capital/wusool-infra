"""POST /desktop/transcripts/corrections — speech-to-text fix suggestions for
the desktop editor. Stateless: nothing is persisted, the user accepts or
rejects each suggestion client-side.
"""

from fastapi import APIRouter, Depends

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import CorrectionServiceDep
from app.modules.meetings.api.schemas import (
    CorrectionSuggestionSchema,
    TranscriptCorrectionsRequest,
    TranscriptCorrectionsResponse,
)
from app.modules.meetings.domain.corrections import TranscriptSegment

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)


@router.post("/transcripts/corrections")
async def suggest_transcript_corrections(
    body: TranscriptCorrectionsRequest, service: CorrectionServiceDep
) -> TranscriptCorrectionsResponse:
    suggestions = await service.suggest(
        [TranscriptSegment(segment_id=s.segment_id, text=s.text) for s in body.segments]
    )
    return TranscriptCorrectionsResponse(
        suggestions=[
            CorrectionSuggestionSchema(
                segment_id=s.segment_id,
                original=s.original,
                suggested=s.suggested,
                reason=s.reason,
            )
            for s in suggestions
        ]
    )
