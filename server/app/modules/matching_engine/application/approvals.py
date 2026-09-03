"""§22-23 approval workflow. Thin — depends on `matching`'s
`MatchResultRepositoryPort` (matching owns `match_results`, via
`MatchingUnitOfWork`) and `matching.domain.status.can_transition`. Every
action re-validates the record and current state against the database;
never trusts a Slack payload's claimed state.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from app.modules.matching_engine.application.ports.unit_of_work import MatchingUnitOfWorkFactory
from app.modules.matching_engine.domain.matching.lifecycle import MatchStatus, can_transition


class MatchNotFoundError(Exception):
    pass


class InvalidTransitionError(Exception):
    """The match is already in a terminal state, or the requested
    transition isn't allowed — state is left unchanged (§23)."""


@dataclass(frozen=True)
class ApprovalResult:
    match_result_id: str
    run_id: str
    seller_org_name: str
    status: str


class ApproveMatchUseCase:
    def __init__(self, uow_factory: MatchingUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, match_result_id: uuid.UUID, approved_by: str) -> ApprovalResult:
        async with self._uow_factory() as uow:
            candidate = await uow.match_results.get_by_id(match_result_id)
            if candidate is None:
                raise MatchNotFoundError(f"match_result {match_result_id} not found")
            if not can_transition(cast(MatchStatus, candidate.status), "APPROVED"):
                raise InvalidTransitionError(
                    f"cannot transition match_result {match_result_id} from "
                    f"{candidate.status} to APPROVED"
                )
            updated = await uow.match_results.update_status(
                match_result_id,
                expected_status="PENDING_REVIEW",
                status="APPROVED",
                approved_by=approved_by,
                decision="APPROVED",
                decided_at=datetime.now(UTC),
            )
        if updated is None:
            raise InvalidTransitionError(
                f"cannot transition match_result {match_result_id} to APPROVED; "
                "it was reviewed concurrently"
            )
        return ApprovalResult(
            match_result_id=updated.id,
            run_id=updated.run_id,
            seller_org_name=updated.seller_org_name or (updated.seller_attio_id or "Unknown"),
            status=updated.status,
        )


class RejectMatchUseCase:
    def __init__(self, uow_factory: MatchingUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, match_result_id: uuid.UUID, approved_by: str, *, notes: str | None = None
    ) -> ApprovalResult:
        async with self._uow_factory() as uow:
            candidate = await uow.match_results.get_by_id(match_result_id)
            if candidate is None:
                raise MatchNotFoundError(f"match_result {match_result_id} not found")
            if not can_transition(cast(MatchStatus, candidate.status), "REJECTED"):
                raise InvalidTransitionError(
                    f"cannot transition match_result {match_result_id} from "
                    f"{candidate.status} to REJECTED"
                )
            updated = await uow.match_results.update_status(
                match_result_id,
                expected_status="PENDING_REVIEW",
                status="REJECTED",
                approved_by=approved_by,
                decision="REJECTED",
                decided_at=datetime.now(UTC),
                decision_notes=notes,
            )
        if updated is None:
            raise InvalidTransitionError(
                f"cannot transition match_result {match_result_id} to REJECTED; "
                "it was reviewed concurrently"
            )
        return ApprovalResult(
            match_result_id=updated.id,
            run_id=updated.run_id,
            seller_org_name=updated.seller_org_name or (updated.seller_attio_id or "Unknown"),
            status=updated.status,
        )
