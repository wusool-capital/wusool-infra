"""Full research on an approved discovered seller, and saving the fields the
advisor picks. The research itself comes from `enrichment` (called by the
web layer); this concern only keeps it on the candidate and guards the save.
"""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.modules.matching_engine.application.base import ServiceBase
from app.modules.matching_engine.application.ports.seller_edits import (
    SellerEditOutcome,
    SellerEditPort,
    SellerEditResult,
    SellerFieldEdit,
)
from app.modules.matching_engine.domain.matching.entities import MatchResultEntity
from app.modules.matching_engine.domain.matching.research import ResearchRecord


class ResearchNotReadyError(Exception):
    """No finished research to act on for this candidate."""


class ResearchAlreadyReviewedError(Exception):
    """The research was already saved or skipped; review happens once."""


class ResearchSaveInProgressError(Exception):
    """Another save of this candidate's research is still running."""


class ResearchMixin(ServiceBase):
    async def get_candidate(self, match_result_id: uuid.UUID) -> MatchResultEntity | None:
        async with self._uow_factory() as uow:
            return await uow.match_results.get_by_id(match_result_id)

    async def claim_research(self, match_result_id: uuid.UUID, *, stale_after: timedelta) -> bool:
        """True for the one caller allowed to research this candidate now."""
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            return await uow.match_results.claim_research(
                match_result_id, now=now, stale_before=now - stale_after
            )

    async def record_research(self, match_result_id: uuid.UUID, record: ResearchRecord) -> None:
        async with self._uow_factory() as uow:
            await uow.match_results.update_research(match_result_id, record)

    async def skip_research(self, match_result_id: uuid.UUID) -> None:
        record = await self._finished_research(match_result_id)
        if record.reviewed:
            raise ResearchAlreadyReviewedError(str(match_result_id))
        await self.record_research(match_result_id, replace(record, skipped=True))

    async def save_research(
        self,
        match_result_id: uuid.UUID,
        *,
        field_names: tuple[str, ...],
        requested_by: str,
        editor: SellerEditPort,
        stale_after: timedelta,
    ) -> SellerEditResult:
        """Writes the chosen proposed fields through `editor`, once at a time,
        and remembers which were saved so they can't be written twice."""
        candidate = await self.get_candidate(match_result_id)
        record = candidate.research if candidate else None
        if candidate is None or record is None or record.outcome != "done":
            raise ResearchNotReadyError(str(match_result_id))
        if record.reviewed:
            raise ResearchAlreadyReviewedError(str(match_result_id))
        chosen = tuple(f for f in record.unsaved() if f.name in field_names)
        if not chosen or candidate.seller_role_id is None:
            return SellerEditResult(outcome=SellerEditOutcome.SAVED)

        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            claimed = await uow.match_results.claim_research_save(
                match_result_id, now=now, stale_before=now - stale_after
            )
        if not claimed:
            raise ResearchSaveInProgressError(str(match_result_id))

        result = SellerEditResult(outcome=SellerEditOutcome.INVALID)
        try:
            result = await editor.apply(
                seller_role_id=candidate.seller_role_id,
                edits=tuple(SellerFieldEdit(f.name, f.target, f.proposed) for f in chosen),
                requested_by=requested_by,
            )
        finally:
            saved = (
                tuple(f.name for f in chosen) if result.outcome is SellerEditOutcome.SAVED else ()
            )
            # Rewriting the record also releases the save claim.
            await self.record_research(match_result_id, record.with_saved(saved))
        return result

    async def _finished_research(self, match_result_id: uuid.UUID) -> ResearchRecord:
        candidate = await self.get_candidate(match_result_id)
        record = candidate.research if candidate else None
        if record is None or record.outcome != "done":
            raise ResearchNotReadyError(str(match_result_id))
        return record
