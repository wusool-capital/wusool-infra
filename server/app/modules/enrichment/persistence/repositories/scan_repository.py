"""Stores one `linkedin_scans` row per attempted scan. Flush-only: the unit
of work commits.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.linkedin_scan import LinkedInScan as LinkedInScanRow
from app.modules.enrichment.domain.linkedin import ScanRecord
from app.modules.enrichment.domain.targets import EnrichmentTargetKind


class ScanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: ScanRecord) -> UUID:
        target, scan = record.target, record.scan
        is_buyer = target.kind is EnrichmentTargetKind.BUYER
        row = LinkedInScanRow(
            org_attio_id=target.org_attio_id,
            buyer_role_id=target.role_id if is_buyer else None,
            seller_role_id=None if is_buyer else target.role_id,
            requested_by=record.requested_by,
            status="failed" if record.failure else "succeeded",
            # The error type only, never its message: it can quote row values.
            error=record.failure,
            posts_found=len(scan.posts),
            job_changes_found=len(scan.job_changes),
            contacts_scanned=scan.contacts_scanned,
            contacts_without_linkedin=len(scan.contacts_without_linkedin),
            started_at=record.started_at,
            finished_at=record.finished_at,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id
