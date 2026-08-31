"""§22-23 approval workflow. Thin — depends on `matching`'s
`MatchResultRepository` (matching owns `match_results`) and
`matching.domain.status.can_transition`. Every action re-validates the
record and current state against the database; never trusts a Slack
payload's claimed state.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.matching.domain.status import MatchStatus, can_transition
from app.modules.matching.infrastructure.repositories import MatchResultRepository


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
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(self, match_result_id: uuid.UUID, approved_by: str) -> ApprovalResult:
        async with self._sessionmaker() as session:
            async with session.begin():
                repo = MatchResultRepository(session)
                candidate = await repo.get_by_id(match_result_id)
                if candidate is None:
                    raise MatchNotFoundError(f"match_result {match_result_id} not found")
                if not can_transition(cast(MatchStatus, candidate.status), "APPROVED"):
                    raise InvalidTransitionError(
                        f"cannot transition match_result {match_result_id} from "
                        f"{candidate.status} to APPROVED"
                    )
                updated = await repo.update_status(
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
            match_result_id=str(updated.id),
            run_id=str(updated.run_id),
            seller_org_name=updated.seller_organization.name
            if updated.seller_organization
            else (updated.seller_attio_id or "Unknown"),
            status=updated.status,
        )


class RejectMatchUseCase:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(
        self, match_result_id: uuid.UUID, approved_by: str, *, notes: str | None = None
    ) -> ApprovalResult:
        async with self._sessionmaker() as session:
            async with session.begin():
                repo = MatchResultRepository(session)
                candidate = await repo.get_by_id(match_result_id)
                if candidate is None:
                    raise MatchNotFoundError(f"match_result {match_result_id} not found")
                if not can_transition(cast(MatchStatus, candidate.status), "REJECTED"):
                    raise InvalidTransitionError(
                        f"cannot transition match_result {match_result_id} from "
                        f"{candidate.status} to REJECTED"
                    )
                updated = await repo.update_status(
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
            match_result_id=str(updated.id),
            run_id=str(updated.run_id),
            seller_org_name=updated.seller_organization.name
            if updated.seller_organization
            else (updated.seller_attio_id or "Unknown"),
            status=updated.status,
        )
