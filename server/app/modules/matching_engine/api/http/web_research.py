"""Full research on a discovered seller approved in the web app: the same
enrichment proposal and LinkedIn scan Slack posts, kept on the candidate row
for review in the page instead.
"""

import asyncio
import logging
import uuid
from dataclasses import replace
from datetime import date, timedelta

from app.modules.enrichment import (
    EnrichmentProposal,
    LinkedInScan,
    ProposedFieldValue,
    WriteTarget,
    propose_for_role,
    scan_linkedin_for_role,
)
from app.modules.matching_engine.api.dependencies import open_matching_engine_service
from app.modules.matching_engine.config import get_settings
from app.modules.matching_engine.domain.matching.research import (
    ResearchField,
    ResearchJobChange,
    ResearchLinkedIn,
    ResearchPost,
    ResearchRecord,
    ResearchTarget,
    ResearchValue,
)

logger = logging.getLogger(__name__)

_TARGETS: dict[WriteTarget, ResearchTarget] = {
    WriteTarget.ORGANIZATION: "organization",
    WriteTarget.SELLER_ROLE: "seller_role",
}


def research_stale_after() -> timedelta:
    return timedelta(minutes=get_settings().match_run_stale_after_minutes)


def _stored(value: ProposedFieldValue) -> ResearchValue:
    proposed = value.proposed
    return proposed.isoformat() if isinstance(proposed, date) else proposed


def _display(value: ResearchValue) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(value)
    if isinstance(value, dict):
        amount, currency = value.get("amount"), value.get("currency")
        return f"{currency} {amount:,.0f}" if isinstance(amount, int | float) else str(value)
    if isinstance(value, float):
        return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}" if value >= 10_000 else str(value)
    return value


def _fields(proposal: EnrichmentProposal) -> tuple[ResearchField, ...]:
    return tuple(
        ResearchField(
            name=v.field_name,
            target=target,
            proposed=_stored(v),
            display=_display(_stored(v)),
            confidence=v.confidence,
            source_url=v.source_url,
            rationale=v.rationale,
        )
        for v in proposal.values
        if (target := _TARGETS.get(v.write_target)) is not None
    )


def _linkedin(scan: LinkedInScan) -> ResearchLinkedIn:
    return ResearchLinkedIn(
        outcome=scan.outcome.value,
        posts=tuple(
            ResearchPost(url=p.url, text=p.text, author_name=p.author_name, posted_at=p.posted_at)
            for p in scan.posts
        ),
        job_changes=tuple(
            ResearchJobChange(
                name=c.contact.name,
                title=c.profile.current_title,
                company=c.profile.current_company,
                source_url=c.source_url,
            )
            for c in scan.job_changes
        ),
        contacts_scanned=scan.contacts_scanned,
        contacts_without_linkedin=len(scan.contacts_without_linkedin),
    )


async def _record(match_result_id: uuid.UUID, record: ResearchRecord) -> None:
    async with open_matching_engine_service() as service:
        await service.record_research(match_result_id, record)


async def research_seller(
    match_result_id: uuid.UUID, *, seller_role_id: str, requested_by: str | None
) -> None:
    """Runs for a claim the caller already holds (`claim_research`), so a second
    click, a retry or a restart can't start a parallel one. Short sessions only:
    the research itself takes ~30s."""
    async with open_matching_engine_service() as service:
        candidate = await service.get_candidate(match_result_id)
    claimed = candidate.research if candidate else None
    if claimed is None:
        return
    base = ResearchRecord(claimed_at=claimed.claimed_at, linkedin=claimed.linkedin)

    async def linkedin() -> ResearchLinkedIn:
        if base.linkedin is not None:
            return base.linkedin
        try:
            scan = await scan_linkedin_for_role(
                kind="seller", role_id=seller_role_id, requested_by=requested_by
            )
            result = _linkedin(scan)
        except Exception:
            logger.exception("web_research_linkedin_failed", extra={"role_id": seller_role_id})
            return ResearchLinkedIn(outcome="failed")
        # Stored at once: a rescan returns only posts it hasn't seen.
        await _record(match_result_id, replace(base, linkedin=result))
        return result

    async def proposal() -> tuple[ResearchField, ...]:
        found = await propose_for_role(kind="seller", role_id=seller_role_id)
        return _fields(found) if found else ()

    linkedin_task = asyncio.create_task(linkedin())
    try:
        fields = await proposal()
        record = replace(base, outcome="done", fields=fields)
    except Exception:
        logger.exception("web_research_failed", extra={"role_id": seller_role_id})
        record = replace(base, outcome="failed", error="Research didn't finish.")
    record = replace(record, linkedin=await linkedin_task)
    await _record(match_result_id, record)
