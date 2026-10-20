"""Stores LinkedIn posts and job changes as `signals`. A signal whose
(`source`, `external_id`) already exists is not new, which is what keeps a
re-run quiet. Flush-only: the unit of work commits.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal
from app.modules.enrichment.domain.linkedin import JobChange, LinkedInPost, job_change_key
from app.modules.enrichment.persistence.signal_payloads import (
    SignalInsert,
    dump_payload,
    job_change_payload,
    post_payload,
)

_SOURCE = "linkedin"


class SignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_new(
        self,
        *,
        org_attio_id: str,
        scan_id: UUID,
        posts: Sequence[LinkedInPost],
        job_changes: Sequence[JobChange],
        now: datetime,
    ) -> set[str]:
        rows: list[SignalInsert] = [
            SignalInsert(
                org_attio_id=org_attio_id,
                source=_SOURCE,
                external_id=p.external_id,
                payload=dump_payload(post_payload(p)),
                ts=p.posted_at or now,
                source_cite=p.url,
                linkedin_scan_id=scan_id,
            )
            for p in posts
        ] + [
            SignalInsert(
                org_attio_id=org_attio_id,
                source=_SOURCE,
                external_id=job_change_key(c),
                payload=dump_payload(job_change_payload(c)),
                ts=now,
                source_cite=c.source_url,
                linkedin_scan_id=scan_id,
            )
            for c in job_changes
        ]
        if not rows:
            return set()
        result = await self._session.execute(
            pg_insert(Signal)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=[Signal.source, Signal.external_id],
                index_where=text("external_id IS NOT NULL"),
            )
            .returning(Signal.external_id)
        )
        return {i for i in result.scalars() if i is not None}
