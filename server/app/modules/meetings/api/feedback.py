"""POST /desktop/feedback — durably records in-app feedback from the
desktop app in `feedback_submissions`, then best-effort emails it via SES
in the background.

The database write is the source of truth and must succeed (a normal 500
if Postgres itself is down, same as any other write endpoint here). Email
is a notification about a row that already exists, not the record itself
-- it's scheduled via `BackgroundTasks` (see `bootstrap.send_feedback_email`)
rather than awaited here, so a misconfigured, throttled, or briefly-down
SES neither loses a user's feedback nor makes them wait for a retry loop
that has nothing to do with whether their submission succeeded. See
`app/models/feedback_submission.py` for the `email_sent`/`email_sent_at`
columns that make a failed notification visible without failing the
request.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import FeedbackMailerDep, FeedbackRepositoryDep
from app.modules.meetings.api.schemas import (
    DesktopFeedbackRequest,
    DesktopFeedbackResponse,
    FeedbackCategory,
)
from app.modules.meetings.bootstrap import send_feedback_email
from app.modules.meetings.config import get_settings
from app.modules.utilities import FixedWindowRateLimiter

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


def _client_ip(request: Request) -> str:
    """The **last** `X-Forwarded-For` entry, not the first -- same
    reasoning as `lead_magnets/api/dependencies.py::client_ip`: Caddy sits
    in front and appends the real peer, so the rightmost value is the
    trustworthy one.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


# Two independent limiters, not one: `install_id` is entirely
# client-supplied (Pydantic only caps its length -- see schemas.py) and
# every desktop install shares one `DESKTOP_API_KEY`, so a caller holding
# that key can trivially defeat an install_id-only limit by sending a
# fresh random id on every request. `_ip_limiter` is the one that actually
# bounds abuse (an IP is far more expensive to rotate); `_install_limiter`
# stays as a courtesy cap on a single well-behaved install retry-looping.
# Either tripping blocks the request.
_install_limiter = FixedWindowRateLimiter(limit=5)
_ip_limiter = FixedWindowRateLimiter(limit=20)


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
    request: DesktopFeedbackRequest,
    http_request: Request,
    repo: FeedbackRepositoryDep,
    mailer: FeedbackMailerDep,
    background_tasks: BackgroundTasks,
) -> DesktopFeedbackResponse:
    # Both checked unconditionally (not `or`-short-circuited) so a request
    # that trips one limiter still counts against the other -- neither
    # counter should undercount just because the other one fired first.
    ip_allowed = _ip_limiter.check(_client_ip(http_request))
    install_allowed = _install_limiter.check(request.install_id)
    if not ip_allowed or not install_allowed:
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
        background_tasks.add_task(
            send_feedback_email,
            mailer=mailer,
            submission_id=submission_id,
            to=recipients,
            from_addr=settings.feedback_email_from,
            subject=build_feedback_email_subject(request),
            body=build_feedback_email_body(request),
        )
    else:
        logger.info(
            "desktop_feedback_email_not_configured",
            extra={"submission_id": str(submission_id)},
        )

    return DesktopFeedbackResponse()
