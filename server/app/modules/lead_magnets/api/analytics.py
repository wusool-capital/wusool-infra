"""Analytics plumbing for the lead tools: the public config the pages load
PostHog from, the tracked Book a Call redirect for emails, and the
`lead_submitted` event.

Nothing here identifies a visitor who did not accept tracking: the server
ignores the visitor id and email unless the page says consent was given.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.modules.lead_magnets.api.dependencies import rate_limit_reads
from app.modules.lead_magnets.api.schemas import AnalyticsContext
from app.modules.lead_magnets.bootstrap import build_analytics
from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.domain.shared.book_call import calendar_url
from app.modules.lead_magnets.domain.shared.lead_event import (
    LeadEvent,
    LeadPerson,
    LeadTool,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["lead-magnets"])


class AnalyticsConfig(BaseModel):
    """Public by design: the project key is meant to sit in page source."""

    enabled: bool
    key: str
    host: str
    assets_host: str
    is_test: bool


@router.get(
    "/analytics/config",
    response_model=AnalyticsConfig,
    dependencies=[Depends(rate_limit_reads)],
)
async def analytics_config(response: Response) -> AnalyticsConfig:
    """What a page needs to load PostHog, fetched only after the visitor consents."""
    settings = get_settings()
    response.headers["Cache-Control"] = "public, max-age=300"
    host = settings.lead_magnet_posthog_host
    return AnalyticsConfig(
        enabled=bool(settings.lead_magnet_posthog_api_key),
        key=settings.lead_magnet_posthog_api_key,
        host=host,
        assets_host=host.replace(".i.posthog.com", "-assets.i.posthog.com"),
        is_test=build_analytics().is_test,
    )


@router.get(
    "/go/book-call/{tool}",
    status_code=302,
    response_class=RedirectResponse,
    dependencies=[Depends(rate_limit_reads)],
)
async def book_call(
    tool: LeadTool,
    background: BackgroundTasks,
    sid: Annotated[str, Query()] = "",
) -> RedirectResponse:
    """The email's Book a Call button. The calendar comes from `tool`, never from
    the link, and the visitor is always redirected even if recording fails."""
    background.add_task(
        capture_lead,
        LeadEvent(
            event="book_call_clicked",
            tool=tool,
            submission_id=sid[:64] or "unknown",
            at=datetime.now(UTC),
            source="email",
        ),
    )
    return RedirectResponse(
        calendar_url(tool), status_code=302, headers={"Cache-Control": "no-store"}
    )


def track_lead(
    background: BackgroundTasks,
    *,
    tool: LeadTool,
    submission_id: str,
    analytics: AnalyticsContext | None,
    name: str | None,
    email: str,
    company: str | None,
) -> None:
    """Sends `lead_submitted` after the response. Anonymous unless the visitor consented."""
    person: LeadPerson | None = None
    visitor_id: str | None = None
    if analytics is not None and analytics.consent:
        person = LeadPerson(name=name or "", email=email, company=company or "")
        visitor_id = analytics.visitor_id
    background.add_task(
        capture_lead,
        LeadEvent(
            event="lead_submitted",
            tool=tool,
            submission_id=submission_id,
            at=datetime.now(UTC),
            person=person,
            visitor_id=visitor_id,
        ),
    )


async def capture_lead(event: LeadEvent) -> None:
    # Built here, not in the request, so a failure can never turn a saved lead into a 500.
    try:
        await build_analytics().capture_lead(event)
    except Exception:
        logger.exception("posthog_capture_failed event=%s", event.event)
