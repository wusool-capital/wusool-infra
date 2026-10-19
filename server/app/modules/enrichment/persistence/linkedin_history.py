"""Stores a LinkedIn scan: a `tool_runs` row for the run, one `signals` row per
new post or job change, and one `activities` event pointing at the run. A
signal that already exists (same `source` + `external_id`) is not new, which
is what keeps a re-run quiet.
"""

import logging
import uuid
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.signal import Signal
from app.models.tool_run import ToolRun
from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivitySource,
    EventType,
    LedgerRef,
    LedgerType,
    LinkedInScanPayload,
    SqlAlchemyActivityRecorder,
    SubjectType,
)
from app.modules.enrichment.domain.linkedin import LinkedInScan, job_change_key
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.persistence.signal_payloads import (
    ScanRunPayload,
    SignalInsert,
    dump_payload,
    job_change_payload,
    post_payload,
)

logger = logging.getLogger(__name__)

TOOL_NAME = "linkedin_scan"
_SOURCE = "linkedin"
_ACTOR = "enrichment"


def _actor(requested_by: str | None) -> ActivityActor:
    if requested_by:
        return ActivityActor.slack(requested_by)
    return ActivityActor.system(_ACTOR)


class SqlAlchemyLinkedInHistory:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def record(
        self,
        target: EnrichmentTarget,
        scan: LinkedInScan,
        *,
        requested_by: str | None = None,
        failure: str | None = None,
    ) -> LinkedInScan:
        now = datetime.now(UTC)
        # The company feed and a contact's feed overlap, so one post can repeat.
        posts = list({p.external_id: p for p in scan.posts}.values())
        changes = list({job_change_key(c): c for c in scan.job_changes}.values())

        async with self._sessionmaker() as session, session.begin():
            run_id = await self._insert_run(
                session, target, scan, posts_n=len(posts), now=now, failure=failure
            )

            rows: list[SignalInsert] = [
                SignalInsert(
                    org_attio_id=target.org_attio_id,
                    source=_SOURCE,
                    external_id=p.external_id,
                    payload=dump_payload(post_payload(p)),
                    ts=p.posted_at or now,
                    source_cite=p.url,
                    tool_run_id=run_id,
                )
                for p in posts
            ] + [
                SignalInsert(
                    org_attio_id=target.org_attio_id,
                    source=_SOURCE,
                    external_id=job_change_key(c),
                    payload=dump_payload(job_change_payload(c)),
                    ts=now,
                    source_cite=c.source_url,
                    tool_run_id=run_id,
                )
                for c in changes
            ]
            new_ids: set[str] = set()
            if rows:
                result = await session.execute(
                    pg_insert(Signal)
                    .values(rows)
                    .on_conflict_do_nothing(
                        index_elements=[Signal.source, Signal.external_id],
                        index_where=text("external_id IS NOT NULL"),
                    )
                    .returning(Signal.external_id)
                )
                new_ids = {i for i in result.scalars() if i is not None}

            new_posts = tuple(p for p in posts if p.external_id in new_ids)
            new_changes = tuple(c for c in changes if job_change_key(c) in new_ids)

            # Every run is history: who triggered it and what it found, even
            # when that is nothing, or when it failed.
            await SqlAlchemyActivityRecorder(session).record(
                ActivityEvent(
                    subject_type=SubjectType.ORGANIZATION,
                    subject_attio_id=target.org_attio_id,
                    event_type=EventType.LINKEDIN_SCAN_COMPLETED,
                    source=ActivitySource.ENRICHMENT,
                    actor=_actor(requested_by),
                    payload=LinkedInScanPayload(
                        new_posts=len(new_posts),
                        new_job_changes=len(new_changes),
                        contacts_scanned=scan.contacts_scanned,
                        contacts_without_linkedin=len(scan.contacts_without_linkedin),
                    ),
                    outcome="failed" if failure else "succeeded",
                    ledger=LedgerRef(LedgerType.TOOL_RUN, run_id),
                    idempotency_key=f"{EventType.LINKEDIN_SCAN_COMPLETED}:{run_id}",
                )
            )
        logger.info(
            "linkedin_history_recorded role=%s new_posts=%d new_job_changes=%d",
            target.role_id,
            len(new_posts),
            len(new_changes),
        )
        return replace(scan, job_changes=new_changes, posts=new_posts)

    @staticmethod
    async def _insert_run(
        session: AsyncSession,
        target: EnrichmentTarget,
        scan: LinkedInScan,
        *,
        posts_n: int,
        now: datetime,
        failure: str | None,
    ) -> uuid.UUID:
        payload = ScanRunPayload(
            posts_found=posts_n,
            job_changes_found=len(scan.job_changes),
            contacts_scanned=scan.contacts_scanned,
            contacts_without_linkedin=len(scan.contacts_without_linkedin),
        )
        is_buyer = target.kind is EnrichmentTargetKind.BUYER
        run = ToolRun(
            tool=TOOL_NAME,
            status="failed" if failure else "succeeded",
            # The error type only, never its message: it can quote row values.
            error=failure,
            started_at=now,
            finished_at=now,
            payload=dump_payload(payload),
            organization_attio_id=target.org_attio_id,
            buyer_role_id=target.role_id if is_buyer else None,
            seller_role_id=None if is_buyer else target.role_id,
        )
        session.add(run)
        await session.flush()
        return run.id
