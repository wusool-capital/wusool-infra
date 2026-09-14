"""POST /desktop/feedback — durably records in-app feedback from the
desktop app in `feedback_submissions`, then best-effort emails it via SES.

The database write is the source of truth and must succeed (a normal 500
if Postgres itself is down, same as any other write endpoint here). Email
is a notification about a row that already exists, not the record itself
-- its failure is logged, not raised, so a misconfigured or briefly-down
SES never loses a user's feedback. See `app/models/feedback_submission.py`
for the `email_sent`/`email_sent_at` columns that make a failed
notification visible without failing the request.
"""

import logging
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import FeedbackMailerDep, FeedbackRepositoryDep
from app.modules.meetings.api.schemas import (
    DesktopFeedbackRequest,
    DesktopFeedbackResponse,
    FeedbackCategory,
)
from app.modules.meetings.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)

_CATEGORY_LABELS: dict[FeedbackCategory, str] = {
    FeedbackCategory.BUG: "Bug",
    FeedbackCategory.FEATURE_REQUEST: "Feature request",
    FeedbackCategory.TRANSCRIPTION_QUALITY: "Transcription quality",
    FeedbackCategory.OTHER: "Other",
}


class _FeedbackRateLimiter:
    """Per-install-id fixed window, in process. One container per
    environment (same reasoning as lead_magnets' copy, which this module
    can't import -- its `__init__.py` declares no `__all__`), so an
    in-process counter is accurate rather than merely convenient. The
    shared `DESKTOP_API_KEY` means any install can otherwise spam this
    table (and, while configured, the inbox behind it).
    """

    def __init__(self, *, limit: int, window_s: int = 3600) -> None:
        self._limit = limit
        self._window_s = window_s
        self._hits: dict[str, tuple[float, int]] = {}

    def check(self, key: str, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        started, count = self._hits.get(key, (now, 0))
        if now - started >= self._window_s:
            started, count = now, 0
        if count >= self._limit:
            return False
        self._hits[key] = (started, count + 1)
        return True


_limiter = _FeedbackRateLimiter(limit=5)


def build_feedback_email_subject(request: DesktopFeedbackRequest) -> str:
    label = _CATEGORY_LABELS[request.category]
    # install_id is free-form (Pydantic only caps its length -- see
    # schemas.py), so strip control characters defensively before it lands
    # in a header field, even though SES's structured Subject.Data field
    # already isn't concatenated the way a raw SMTP header would be.
    install_id = "".join(ch for ch in request.install_id if ch not in "\r\n")
    return f"Scribe feedback ({label}) from {install_id}"


def build_feedback_email_body(request: DesktopFeedbackRequest) -> str:
    """Pure -- no FastAPI/SES client -- so it's unit-testable directly."""
    label = _CATEGORY_LABELS[request.category]
    lines = [
        f"Category: {label}",
        "",
        request.message,
        "",
        f"Install ID: {request.install_id}",
        f"App version: {request.app_version}",
        f"Platform: {request.platform}",
    ]
    if request.contact:
        lines.append(f"Contact: {request.contact}")
    return "\n".join(lines)


@router.post("/feedback")
async def submit_feedback(
    request: DesktopFeedbackRequest, repo: FeedbackRepositoryDep, mailer: FeedbackMailerDep
) -> DesktopFeedbackResponse:
    if not _limiter.check(request.install_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many feedback submissions",
        )

    submission_id = uuid4()
    await repo.create(
        id=submission_id,
        category=request.category.value,
        message=request.message,
        contact=request.contact,
        install_id=request.install_id,
        app_version=request.app_version,
        platform=request.platform,
    )

    settings = get_settings()
    recipients = settings.feedback_email_to.split()
    if recipients and settings.feedback_email_from:
        try:
            await mailer.send(
                to=recipients,
                from_addr=settings.feedback_email_from,
                subject=build_feedback_email_subject(request),
                body=build_feedback_email_body(request),
            )
        except Exception:
            logger.exception(
                "desktop_feedback_email_failed",
                extra={"install_id": request.install_id, "submission_id": str(submission_id)},
            )
        else:
            await repo.mark_email_sent(id=submission_id)
    else:
        logger.info(
            "desktop_feedback_email_not_configured",
            extra={"submission_id": str(submission_id)},
        )

    return DesktopFeedbackResponse()
