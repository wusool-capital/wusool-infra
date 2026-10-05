"""Gated insights reports (PRD 3): the preview, the unlock, and the Sanity
publish webhook that keeps the Webflow card in step.

The report page calls the first two from its iframe on this host, so they
are same-origin. Only the unlock carries the origin check, because browsers
omit `Origin` on a same-origin GET. Page views get their own, larger per-IP
budget (`rate_limit_reads`), so reading never uses up a reader's unlock.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    HTTPException,
    Path,
    Request,
    Response,
    status,
)

from app.modules.lead_magnets.api.dependencies import (
    SANITY_SIGNATURE_HEADER,
    SessionDep,
    is_valid_sanity_signature,
    rate_limit,
    rate_limit_reads,
    require_allowed_origin,
)
from app.modules.lead_magnets.api.schemas import (
    ReportResponse,
    ReportUnlockRequest,
    SanityWebhookBody,
)
from app.modules.lead_magnets.application.shared.ports import ReportSourcePort
from app.modules.lead_magnets.bootstrap import (
    build_report_source,
    build_report_sync,
    build_submission_service,
    build_tool_runs,
    run_completion,
)
from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.domain.insights_report.report import ReportDocument, org_domain
from app.modules.lead_magnets.domain.insights_report.split import split_report
from app.modules.lead_magnets.domain.shared.schemas import AttioIdentityPayload

logger = logging.getLogger(__name__)

READER_COOKIE = "wusool_reader"
_READER_COOKIE_MAX_AGE_S = 365 * 24 * 3600
_TOOL = "insights_report"

router = APIRouter(tags=["lead-magnets"])

Slug = Annotated[str, Path(pattern=r"^[a-z0-9-]{1,256}$")]


def get_report_source() -> ReportSourcePort:
    if not get_settings().lead_magnet_sanity_project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "reports are not configured")
    return build_report_source()


SourceDep = Annotated[ReportSourcePort, Depends(get_report_source)]


async def _published(source: ReportSourcePort, slug: str) -> ReportDocument:
    report = await source.get(slug)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    return report


@router.get(
    "/reports/{slug}", response_model=ReportResponse, dependencies=[Depends(rate_limit_reads)]
)
async def read_report(
    slug: Slug,
    source: SourceDep,
    session: SessionDep,
    background: BackgroundTasks,
    response: Response,
    wusool_reader: Annotated[str | None, Cookie()] = None,
) -> ReportResponse:
    """The preview, or the whole report for a returning reader.

    A returning reader's first visit to a *different* report records its own
    run, so each report read is one interaction for PRD 2. The
    `<reader>:<slug>` submission id makes repeat visits reuse that row.
    """
    report = await _published(source, slug)
    # The body depends on the cookie, so no shared cache may store it.
    response.headers["Cache-Control"] = "no-store"

    reader = await _known_reader(session, wusool_reader)
    if reader is None:
        preview, _ = split_report(report.html)
        return ReportResponse(title=report.title, html=preview, locked=True)

    identity, unlocked_slug = reader
    if unlocked_slug != slug:
        run_id = await build_submission_service(session).record(
            tool=_TOOL,
            payload={
                "submission_id": f"{wusool_reader}:{slug}",
                **identity.model_dump(include={"name", "email", "company", "domain"}),
                "slug": slug,
                "report_title": report.title,
            },
            email=identity.email,
            domain=identity.domain,
        )
        await session.commit()
        background.add_task(run_completion, run_id)
    return ReportResponse(title=report.title, html=report.html, locked=False)


@router.post(
    "/reports/{slug}/unlock",
    response_model=ReportResponse,
    dependencies=[Depends(require_allowed_origin), Depends(rate_limit)],
)
async def unlock_report(
    slug: Slug,
    request: ReportUnlockRequest,
    source: SourceDep,
    session: SessionDep,
    background: BackgroundTasks,
    response: Response,
) -> ReportResponse:
    """Same write contract as `/get-started`: record, respond, then write
    Attio in the background. The reader gets the full report either way."""
    report = await _published(source, slug)
    domain = org_domain(request.email)
    run_id = await build_submission_service(session).record(
        tool=_TOOL,
        payload={
            **request.model_dump(),
            "domain": domain,
            "slug": slug,
            "report_title": report.title,
        },
        email=request.email,
        domain=domain,
    )
    await session.commit()
    background.add_task(run_completion, run_id)

    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        READER_COOKIE,
        str(run_id),
        max_age=_READER_COOKIE_MAX_AGE_S,
        path="/reports",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return ReportResponse(title=report.title, html=report.html, locked=False)


@router.post("/reports/webhooks/sanity", status_code=status.HTTP_204_NO_CONTENT)
async def sanity_webhook(request: Request) -> None:
    """Sanity's publish webhook. A Webflow failure surfaces as a 5xx on
    purpose, so Sanity retries the delivery."""
    settings = get_settings()
    if not (
        settings.lead_magnet_sanity_project_id
        and settings.lead_magnet_sanity_webhook_secret
        and settings.lead_magnet_sanity_write_token
        and settings.lead_magnet_webflow_api_token
    ):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "report sync is not configured")

    body = await request.body()
    secret = settings.lead_magnet_sanity_webhook_secret
    if not is_valid_sanity_signature(body, request.headers.get(SANITY_SIGNATURE_HEADER), secret):
        logger.warning("insights_report_webhook_bad_signature")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid signature")

    event = SanityWebhookBody.model_validate_json(body)
    await build_report_sync().sync(
        slug=event.slug,
        previous_slug=event.previous_slug,
        featured_changed=event.featured_changed,
    )


async def _known_reader(
    session: SessionDep, cookie: str | None
) -> tuple[AttioIdentityPayload, str] | None:
    """The identity and report slug behind a reader cookie, or `None`."""
    if not cookie:
        return None
    try:
        run_id = UUID(cookie)
    except ValueError:
        return None
    run = await build_tool_runs(session).get(run_id)
    if run is None or run.tool != _TOOL:
        return None
    slug = run.payload.get("slug")
    return AttioIdentityPayload.model_validate(run.payload), slug if isinstance(slug, str) else ""
