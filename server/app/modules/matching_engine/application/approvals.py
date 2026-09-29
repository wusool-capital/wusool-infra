"""§22-23 approval workflow. Thin — depends on `matching`'s
`MatchResultRepositoryPort` (matching owns `match_results`, via
`MatchingUnitOfWork`) and `matching.domain.status.can_transition`. Every
action re-validates the record and current state against the database;
never trusts a Slack payload's claimed state.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast

from app.modules.matching_engine.application.base import ServiceBase
from app.modules.matching_engine.application.errors import (
    DealGatewayError,
    ExistingDealsFoundError,
    PartialWriteError,
)
from app.modules.matching_engine.domain.matching.deals import (
    INBOUND_STAGE,
    QUALIFIED_STAGE,
    DealRecord,
    DealResolution,
    ExistingDeal,
    QualifiedDealDraft,
)
from app.modules.matching_engine.domain.matching.entities import MatchResultEntity
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


class ApprovalsMixin(ServiceBase):
    async def approve_match(
        self,
        match_result_id: uuid.UUID,
        approved_by: str,
        *,
        resolution: DealResolution | None = None,
        existing_deal_id: str | None = None,
    ) -> ApprovalResult:
        """Attio first, then one Postgres transaction: `Deal.attio_id` is the
        deals primary key, so the Attio record must exist before any row can.
        There is no distributed transaction — an Attio write that lands
        before a Postgres failure surfaces as `PartialWriteError`, and the
        inbound webhook / nightly resync reconciles the orphan.
        """
        # The candidate row stays locked through the Attio write, so a
        # concurrent approval waits, then sees it decided and never creates
        # a second deal.
        async with self._uow_factory() as uow:
            candidate = await uow.match_results.get_by_id_for_update(match_result_id)
            if candidate is None:
                raise MatchNotFoundError(f"match_result {match_result_id} not found")
            if not can_transition(cast(MatchStatus, candidate.status), "APPROVED"):
                raise InvalidTransitionError(
                    f"cannot transition match_result {match_result_id} from "
                    f"{candidate.status} to APPROVED"
                )
            if candidate.seller_attio_id is None:
                raise InvalidTransitionError(
                    f"match_result {match_result_id} has no seller to approve"
                )

            deal, landed = await self._write_attio_deal(
                candidate, candidate.seller_attio_id, resolution, existing_deal_id
            )

            record = DealRecord(
                attio_id=deal.attio_id,
                name=deal.name,
                stage=deal.stage,
                buyer_attio_id=candidate.buyer_attio_id,
                seller_attio_id=candidate.seller_attio_id,
            )
            try:
                await uow.deals.upsert(record)
                updated = await uow.match_results.update_status(
                    match_result_id,
                    expected_status="PENDING_REVIEW",
                    status="APPROVED",
                    approved_by=approved_by,
                    decision="APPROVED",
                    decided_at=datetime.now(UTC),
                    deal_attio_id=deal.attio_id,
                )
                if updated is None:
                    raise InvalidTransitionError(
                        f"cannot transition match_result {match_result_id} to APPROVED; "
                        "it was reviewed concurrently"
                    )
            except Exception as exc:
                raise PartialWriteError(landed, exc) from exc
        return ApprovalResult(
            match_result_id=updated.id,
            run_id=updated.run_id,
            seller_org_name=updated.seller_org_name or (updated.seller_attio_id or "Unknown"),
            status=updated.status,
        )

    async def _write_attio_deal(
        self,
        candidate: MatchResultEntity,
        seller_attio_id: str,
        resolution: DealResolution | None,
        existing_deal_id: str | None,
    ) -> tuple[ExistingDeal, list[str]]:
        try:
            chosen: ExistingDeal | None = None
            if resolution != "create_new":
                existing = await self._deal_gateway.find_pair_deals(
                    buyer_attio_id=candidate.buyer_attio_id, seller_attio_id=seller_attio_id
                )
                if existing and resolution is None:
                    raise ExistingDealsFoundError(existing)
                chosen = next((d for d in existing if d.attio_id == existing_deal_id), None)
                if resolution == "promote_existing" and chosen is None and existing:
                    # The chosen deal changed since the prompt — ask again.
                    raise ExistingDealsFoundError(existing)

            if chosen is not None:
                # Only Inbound moves up; a deal already further along must not regress.
                if chosen.stage == INBOUND_STAGE:
                    await self._deal_gateway.promote_to_qualified(chosen.attio_id)
                    chosen = replace(chosen, stage=QUALIFIED_STAGE)
                return chosen, [f"deal '{chosen.name}' in Attio (record_id={chosen.attio_id})"]

            draft = QualifiedDealDraft(
                name=f"{candidate.seller_org_name or seller_attio_id} - "
                f"{candidate.buyer_org_name or candidate.buyer_attio_id}",
                buyer_attio_id=candidate.buyer_attio_id,
                seller_attio_id=seller_attio_id,
            )
            created = await self._deal_gateway.create_qualified(draft)
            return created, [
                f"deal '{created.name}' created in Attio (record_id={created.attio_id})"
            ]
        except DealGatewayError as exc:
            raise PartialWriteError([], exc) from exc

    async def reject_match(
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
