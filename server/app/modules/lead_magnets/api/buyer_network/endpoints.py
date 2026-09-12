"""The `/buyer/apply` endpoint.

Follows the write contract: record the application, respond to the visitor,
then do everything that can fail — the Attio write and the best-effort
qualification note — in the background. Nothing after the response can lose
the application.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.modules.lead_magnets.api.dependencies import (
    SessionDep,
    rate_limit,
    require_allowed_origin,
)
from app.modules.lead_magnets.api.schemas import BuyerApplyRequest, BuyerApplyResponse
from app.modules.lead_magnets.bootstrap import build_submission_service, run_completion

router = APIRouter(
    tags=["lead-magnets"],
    dependencies=[Depends(require_allowed_origin), Depends(rate_limit)],
)


@router.post("/buyer/apply", response_model=BuyerApplyResponse)
async def buyer_apply(
    request: BuyerApplyRequest, session: SessionDep, background: BackgroundTasks
) -> BuyerApplyResponse:
    """The Buyer Network application.

    Unlike readiness, nothing here depends on a model call to respond —
    `org_type`/`target_geography`/`sector_focus` are validated against
    Attio's live option lists in the background write, not eagerly: a bad
    value there must fail the write, not the record, or a CRM-vocabulary
    typo would reproduce the exact lead-loss bug this migration exists to
    fix.
    """
    service = build_submission_service(session)
    run_id, is_new = await service.record(
        tool="buyer_network",
        payload=request.model_dump(),
        email=request.email,
        domain=request.domain,
    )
    await session.commit()

    if not is_new:
        raise HTTPException(status.HTTP_409_CONFLICT, "you have already completed this")

    background.add_task(run_completion, run_id)

    return BuyerApplyResponse(ok=True, run_id=str(run_id))
