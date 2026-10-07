"""Gated insights reports (PRD 3): the preview, the emailed-code unlock, the
PDF download, and the Sanity publish webhook that keeps the Webflow card in step.

The report page calls these from its iframe on this host, so they are
same-origin. Only the unlock POSTs carry the origin check, because browsers
omit `Origin` on a same-origin GET. Page views get their own, larger per-IP
budget (`rate_limit_reads`), so reading never uses up a reader's unlock.
"""

import logging
from dataclasses import asdict
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
    rate_limit_downloads,
    rate_limit_reads,
    require_allowed_origin,
)
from app.modules.lead_magnets.api.schemas import (
    ReportCodeSent,
    ReportResponse,
    ReportUnlockRequest,
    ReportVerifyRequest,
    SanityWebhookBody,
)
from app.modules.lead_magnets.application.insights_report.unlock import (
    ChallengeGone,
    CodeNotSent,
    TooManyCodes,
    WrongCode,
)
from app.modules.lead_magnets.application.shared.ports import ReportSourcePort
from app.modules.lead_magnets.bootstrap import (
    build_article_sync,
    build_report_renderer,
    build_report_source,
    build_report_sync,
    build_report_unlock,
    build_submission_service,
    build_tool_runs,
    run_completion,
)
from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.domain.insights_report.report import ReportDocument, org_domain
from app.modules.lead_magnets.domain.insights_report.unlock import ReaderForm
from app.modules.lead_magnets.domain.shared.schemas import AttioIdentityPayload

logger = logging.getLogger(__name__)

READER_COOKIE = "wusool_reader"
_READER_COOKIE_MAX_AGE_S = 365 * 24 * 3600
_TOOL = "insights_report"
# Kept as `insights_report_sync_failed` for reports, which existing log searches use.
_SYNC_LOG = {"report": "insights_report", "insights": "insights_article"}

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
    """The preview, or the whole report for a returning reader."""
    report = await _published(source, slug)
    # The body depends on the cookie, so no shared cache may store it.
    response.headers["Cache-Control"] = "no-store"

    if not await _record_read(session, background, report, wusool_reader):
        return ReportResponse(
            title=report.title, html=report.html[: report.preview_end], locked=True
        )
    return ReportResponse(title=report.title, html=report.html, locked=False)


@router.get(
    "/reports/{slug}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    dependencies=[Depends(rate_limit_downloads)],
)
async def download_report_pdf(
    slug: Slug,
    source: SourceDep,
    session: SessionDep,
    background: BackgroundTasks,
    wusool_reader: Annotated[str | None, Cookie()] = None,
) -> Response:
    """The whole report as a PDF, for unlocked readers only. Printed on each
    download, on its own per-IP budget, because each one launches Chromium."""
    report = await _published(source, slug)
    if not await _record_read(session, background, report, wusool_reader):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "unlock the report first")
    try:
        pdf = await build_report_renderer().pdf(report.html)
    except TimeoutError:
        logger.warning("insights_report_pdf_timeout slug=%s", slug)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "busy, try again") from None
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{slug}.pdf"',
            "Cache-Control": "no-store",
        },
    )


async def _record_read(
    session: SessionDep,
    background: BackgroundTasks,
    report: ReportDocument,
    cookie: str | None,
) -> bool:
    """Whether the cookie belongs to a reader who unlocked a report.

    A returning reader's first visit to a *different* report records its own
    run, so each report read is one interaction for PRD 2. The
    `<reader>:<slug>` submission id makes repeat visits reuse that row.
    """
    reader = await _known_reader(session, cookie)
    if reader is None:
        return False
    identity, unlocked_slug = reader
    if unlocked_slug != report.slug:
        run_id = await build_submission_service(session).record(
            tool=_TOOL,
            payload={
                "submission_id": f"{cookie}:{report.slug}",
                **identity.model_dump(include={"name", "email", "company", "domain"}),
                "slug": report.slug,
                "report_title": report.title,
            },
            email=identity.email,
            domain=identity.domain,
        )
        await session.commit()
        background.add_task(run_completion, run_id)
    return True


@router.post(
    "/reports/{slug}/unlock",
    response_model=ReportCodeSent | ReportResponse,
    dependencies=[Depends(require_allowed_origin), Depends(rate_limit)],
)
async def unlock_report(
    slug: Slug,
    request: ReportUnlockRequest,
    source: SourceDep,
    session: SessionDep,
    background: BackgroundTasks,
    response: Response,
) -> ReportCodeSent | ReportResponse:
    """Step one of the gate: email the reader a code. Nothing is recorded yet.
    With email verification off, the report opens straight away instead."""
    report = await _published(source, slug)
    form = ReaderForm(**request.model_dump())
    if not get_settings().lead_magnet_report_email_otp:
        return await _open_report(session, background, response, report, form)
    try:
        challenge_id = await build_report_unlock().send_code(
            slug=slug, report_title=report.title, form=form
        )
    except TooManyCodes:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many codes") from None
    except CodeNotSent:
        logger.exception("insights_report_code_email_failed slug=%s", slug)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "could not send code") from None
    return ReportCodeSent(challenge_id=challenge_id)


@router.post(
    "/reports/{slug}/unlock/verify",
    response_model=ReportResponse,
    # Cheap and capped at five guesses per code, so it takes the larger read budget.
    dependencies=[Depends(require_allowed_origin), Depends(rate_limit_reads)],
)
async def verify_report_unlock(
    slug: Slug,
    request: ReportVerifyRequest,
    source: SourceDep,
    session: SessionDep,
    background: BackgroundTasks,
    response: Response,
) -> ReportResponse:
    """Step two: a matching code opens the report."""
    report = await _published(source, slug)
    unlock = build_report_unlock()
    try:
        form = unlock.verify(slug=slug, challenge_id=request.challenge_id, code=request.code)
    except WrongCode:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "wrong code") from None
    except ChallengeGone:
        raise HTTPException(status.HTTP_410_GONE, "code expired") from None

    opened = await _open_report(session, background, response, report, form)
    unlock.spend(request.challenge_id)
    return opened


async def _open_report(
    session: SessionDep,
    background: BackgroundTasks,
    response: Response,
    report: ReportDocument,
    form: ReaderForm,
) -> ReportResponse:
    """Records the lead, as `/get-started` does, and sets the reader cookie.
    Attio is written in the background."""
    domain = org_domain(form.email)
    run_id = await build_submission_service(session).record(
        tool=_TOOL,
        payload={
            **asdict(form),
            "domain": domain,
            "slug": report.slug,
            "report_title": report.title,
        },
        email=form.email,
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


@router.post("/reports/webhooks/sanity", status_code=status.HTTP_202_ACCEPTED)
async def sanity_webhook(request: Request, background: BackgroundTasks) -> None:
    """Sanity's publish webhook, for reports and Insights articles alike (the Free
    plan allows only two webhooks: dev and prod). Accepted at once and synced in
    the background: a render plus Webflow calls can approach Sanity's 30 s
    timeout, and its retry would race the first sync to create the same item.
    A failed sync is logged, and the next publish of that document repairs it."""
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
    background.add_task(_sync, event)


async def _sync(event: SanityWebhookBody) -> None:
    try:
        if event.type == "insights":
            await build_article_sync().sync(slug=event.slug, previous_slug=event.previous_slug)
        else:
            await build_report_sync().sync(
                slug=event.slug,
                previous_slug=event.previous_slug,
                featured_changed=event.featured_changed,
            )
    except Exception:
        logger.exception("%s_sync_failed slug=%s", _SYNC_LOG[event.type], event.slug)


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
