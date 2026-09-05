"""POST /desktop/meetings — the desktop app's transcript push. Acks fast:
`ingest_meeting` only creates the `meetings` row (status=summarizing); the
actual LLM call is scheduled as a `BackgroundTasks` job right after,
matching `ddl_commands/api/attio_sync.py`'s ack-then-background-work
pattern — the desktop app never waits on summarization to finish.

`MeetingAlreadyExistsError` (409) and `UnknownCompanyReferenceError` (422),
both raised by `ingest_meeting`, are left to propagate — the registered
`AppError` exception handler turns them into the right response; this
route never returns `already_existed=True` because a true duplicate raises
409 instead of returning 200.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import MeetingsServiceDep, SessionDep
from app.modules.meetings.api.schemas import (
    DesktopMeetingSubmitRequest,
    DesktopMeetingSubmitResponse,
)
from app.modules.meetings.bootstrap import run_summarize_and_publish
from app.modules.meetings.config import get_settings
from app.modules.meetings.domain.rendering import TranscriptTurn
from app.modules.meetings.domain.roles import MeetingRole

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)

_ROLE_FIELDS: tuple[tuple[MeetingRole, str, str], ...] = (
    (MeetingRole.SELLER, "seller_selection", "seller_query"),
    (MeetingRole.BUYER, "buyer_selection", "buyer_query"),
    (MeetingRole.INVESTOR, "investor_selection", "investor_query"),
    (MeetingRole.INTERNAL, "internal_selection", "internal_query"),
    (MeetingRole.GENERAL, "general_selection", "general_query"),
)


def _role_dicts(
    request: DesktopMeetingSubmitRequest,
) -> tuple[dict[MeetingRole, str], dict[MeetingRole, str]]:
    selections: dict[MeetingRole, str] = {}
    queries: dict[MeetingRole, str] = {}
    for role, selection_field, query_field in _ROLE_FIELDS:
        selection = getattr(request, selection_field)
        query = getattr(request, query_field)
        if selection:
            selections[role] = selection
        if query:
            queries[role] = query
    return selections, queries


@router.post("/meetings")
async def submit_meeting(
    request: DesktopMeetingSubmitRequest,
    background_tasks: BackgroundTasks,
    service: MeetingsServiceDep,
    session: SessionDep,
) -> DesktopMeetingSubmitResponse:
    transcript_chars = sum(len(turn.text) for turn in request.transcript)
    if transcript_chars > get_settings().max_transcript_chars:
        raise HTTPException(status_code=422, detail="Transcript exceeds maximum allowed size")

    role_selections, role_queries = _role_dicts(request)
    meeting = await service.ingest_meeting(
        install_id=request.install_id,
        local_recording_id=request.local_recording_id,
        transcript=[
            TranscriptTurn(speaker=turn.speaker, text=turn.text) for turn in request.transcript
        ],
        duration_seconds=request.duration_seconds,
        role_selections=role_selections,
        role_queries=role_queries,
    )
    # Commit explicitly, here, before scheduling the background task: this
    # FastAPI version runs BackgroundTasks BEFORE a yield-dependency's
    # post-yield cleanup (confirmed live — `get_session`'s own commit
    # otherwise runs strictly after `run_summarize_and_publish` has already
    # started, so its independent session couldn't see this row at all,
    # yielding `summarize_and_publish_meeting_not_found` on every push).
    # Not `service.summarize_and_publish` — that service's session is
    # committed/closed once this endpoint returns, before a background
    # task is guaranteed to run. `run_summarize_and_publish` opens its own
    # session (see its docstring).
    await session.commit()
    background_tasks.add_task(run_summarize_and_publish, meeting.id)
    return DesktopMeetingSubmitResponse(
        meeting_id=meeting.id, status=meeting.status, already_existed=False
    )
