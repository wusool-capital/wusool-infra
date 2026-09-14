"""POST /desktop/feedback — relays in-app feedback from the desktop app to
an email inbox via SES. No row is ever written (see
`application/errors.py`'s `FeedbackDeliveryNotConfiguredError`/
`FeedbackDeliveryFailedError` docstrings): the inbox is the triage
mechanism, so delivery happens synchronously and a failure is a real
error, not `BackgroundTasks` fire-and-forget -- backgrounding it would let
the client see 200 while the user's typed text is silently lost.
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import FeedbackMailerDep
from app.modules.meetings.api.schemas import (
    DesktopFeedbackRequest,
    DesktopFeedbackResponse,
    FeedbackCategory,
)
from app.modules.meetings.application.errors import (
    FeedbackDeliveryFailedError,
    FeedbackDeliveryNotConfiguredError,
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
    inbox.
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
    request: DesktopFeedbackRequest, mailer: FeedbackMailerDep
) -> DesktopFeedbackResponse:
    settings = get_settings()
    if not settings.feedback_email_to or not settings.feedback_email_from:
        raise FeedbackDeliveryNotConfiguredError("Feedback delivery is not configured")

    if not _limiter.check(request.install_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many feedback submissions",
        )

    try:
        await mailer.send(
            to=settings.feedback_email_to,
            from_addr=settings.feedback_email_from,
            subject=build_feedback_email_subject(request),
            body=build_feedback_email_body(request),
        )
    except Exception as exc:
        logger.exception(
            "desktop_feedback_delivery_failed", extra={"install_id": request.install_id}
        )
        raise FeedbackDeliveryFailedError("Could not deliver feedback by email") from exc

    return DesktopFeedbackResponse()
