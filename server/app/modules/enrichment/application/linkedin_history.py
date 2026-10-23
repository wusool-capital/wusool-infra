"""What a LinkedIn scan leaves behind: one scan row, a signal per new post or
job change, and one activity pointing at the scan — written in one unit of
work. Returns only what is new, so a re-run reports nothing it already has.
"""

import logging
from dataclasses import replace

from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivitySource,
    EventType,
    LedgerRef,
    LedgerType,
    LinkedInScanPayload,
    SubjectType,
)
from app.modules.enrichment.application.ports.linkedin_unit_of_work import (
    LinkedInHistoryUnitOfWorkFactory,
)
from app.modules.enrichment.domain.linkedin import LinkedInScan, ScanRecord, job_change_key

logger = logging.getLogger(__name__)

_ACTOR = "enrichment"


def _actor(requested_by: str | None) -> ActivityActor:
    if requested_by:
        return ActivityActor.slack(requested_by)
    return ActivityActor.system(_ACTOR)


async def record_scan(
    uow_factory: LinkedInHistoryUnitOfWorkFactory, record: ScanRecord
) -> LinkedInScan:
    """Raises on a storage failure: the caller decides whether to fall back."""
    target, scan = record.target, record.scan
    # The company feed and a contact's feed overlap, so one post can repeat.
    posts = tuple({p.external_id: p for p in scan.posts}.values())
    changes = tuple({job_change_key(c): c for c in scan.job_changes}.values())

    async with uow_factory() as uow:
        scan_id = await uow.scans.add(
            replace(record, scan=replace(scan, posts=posts, job_changes=changes))
        )
        new_ids = await uow.signals.add_new(
            org_attio_id=target.org_attio_id,
            scan_id=scan_id,
            posts=posts,
            job_changes=changes,
            now=record.finished_at,
        )
        new_posts = tuple(p for p in posts if p.external_id in new_ids)
        new_changes = tuple(c for c in changes if job_change_key(c) in new_ids)

        # Every run is history: who triggered it and what it found, even when
        # that is nothing, or when it failed.
        await uow.activities.record(
            ActivityEvent(
                subject_type=SubjectType.ORGANIZATION,
                subject_attio_id=target.org_attio_id,
                event_type=EventType.LINKEDIN_SCAN_COMPLETED,
                source=ActivitySource.ENRICHMENT,
                actor=_actor(record.requested_by),
                payload=LinkedInScanPayload(
                    new_posts=len(new_posts),
                    new_job_changes=len(new_changes),
                    contacts_scanned=scan.contacts_scanned,
                    contacts_without_linkedin=len(scan.contacts_without_linkedin),
                ),
                outcome="failed" if record.failure else "succeeded",
                ledger=LedgerRef(LedgerType.LINKEDIN_SCAN, scan_id),
                idempotency_key=f"{EventType.LINKEDIN_SCAN_COMPLETED}:{scan_id}",
            )
        )
    logger.info(
        "linkedin_history_recorded role=%s new_posts=%d new_job_changes=%d",
        target.role_id,
        len(new_posts),
        len(new_changes),
    )
    return replace(scan, job_changes=new_changes, posts=new_posts)
