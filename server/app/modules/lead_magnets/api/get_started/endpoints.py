"""The `/get-started` endpoint.

Follows the write contract: record the submission, respond to the visitor,
then do the Attio write in the background. Nothing after the response can
lose the lead.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.modules.lead_magnets.api.dependencies import (
    SessionDep,
    rate_limit,
    require_allowed_origin,
)
from app.modules.lead_magnets.api.schemas import GetStartedRequest, GetStartedResponse
from app.modules.lead_magnets.bootstrap import build_submission_service, run_completion

router = APIRouter(
    tags=["lead-magnets"],
    dependencies=[Depends(require_allowed_origin), Depends(rate_limit)],
)


@router.post("/get-started", response_model=GetStartedResponse)
async def get_started(
    request: GetStartedRequest, session: SessionDep, background: BackgroundTasks
) -> GetStartedResponse:
    """The Get Started lead form.

    No model call and nothing computed — the fastest of the five tools to
    respond, and the only one whose entire output is an acknowledgement.
    `sector`/`sell_timeline` are validated against Attio's option lists in
    the background write, not eagerly: a bad value there must fail the write
    rather than the record.
    """
    payload = request.model_dump()
    # The "Other" sector's free text has no CRM field of its own, and
    # `sector` itself must stay a mappable option title. Folding it into the
    # organisation's description is what puts it in front of a human instead
    # of leaving it in `tool_runs.payload` — `AttioIdentityPayload` already
    # reads `description`, so no writer changes. Same shape of derived key as
    # readiness's `score`.
    #
    # Gated on `sector == "Other"`, not on `sector_other` alone: the page
    # clears the free-text box whenever a real sector is picked, but a
    # request need not come from the page. Without this check a crafted
    # submission could leave `sector` mapped to a real option while still
    # writing a "self-described" description that contradicts it.
    if request.sector == "Other" and request.sector_other:
        payload["description"] = f"Sector (self-described): {request.sector_other}"

    service = build_submission_service(session)
    run_id, outcome = await service.record(
        tool="get_started",
        payload=payload,
        email=request.email,
        domain=request.domain,
    )
    await session.commit()

    if outcome == "duplicate":
        raise HTTPException(status.HTTP_409_CONFLICT, "you have already completed this")
    # "replay" is handled like "new": `run_completion` is idempotent
    # against a run that already finished.

    background.add_task(run_completion, run_id)

    return GetStartedResponse(ok=True, run_id=str(run_id))
