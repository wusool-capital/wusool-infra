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
from app.modules.meetings.domain.corrections import CorrectionContext, TranscriptSegment

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)


@router.post("/transcripts/corrections")
async def suggest_transcript_corrections(
    body: TranscriptCorrectionsRequest, service: CorrectionServiceDep
) -> TranscriptCorrectionsResponse:
    context = (
        CorrectionContext(
            title=body.context.title,
            names=tuple(body.context.names),
            vocabulary=tuple(body.context.vocabulary),
        )
        if body.context
        else None
    )
    result = await service.suggest(
        [
            TranscriptSegment(segment_id=s.segment_id, text=s.text, speaker=s.speaker)
            for s in body.segments
        ],
        context,
    )
    return TranscriptCorrectionsResponse(
        suggestions=[
            CorrectionSuggestionSchema(
                segment_id=s.segment_id,
                original=s.original,
                suggested=s.suggested,
                category=s.category,
                reason=s.reason,
            )
            for s in result.suggestions
        ],
        checked_segments=result.checked_segments,
        failed_segment_ids=result.failed_segment_ids,
    )
