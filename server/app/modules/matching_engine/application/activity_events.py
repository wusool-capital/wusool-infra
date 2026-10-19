"""Builds the `activities` events a match run and a review decision record."""

import uuid

from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivitySource,
    EventType,
    LedgerRef,
    LedgerType,
    MatchDecisionPayload,
    MatchRunPayload,
    SubjectType,
)
from app.modules.matching_engine.domain.matching.entities import MatchResultEntity


def matching_actor(slack_user_id: str | None) -> ActivityActor:
    if slack_user_id:
        return ActivityActor.slack(slack_user_id)
    return ActivityActor.system("matching_engine")


def run_completed_event(
    *,
    run_id: uuid.UUID,
    header_row_id: str,
    buyer_role_id: uuid.UUID,
    requested_by: str | None,
    status: str,
    candidate_count: int,
) -> ActivityEvent:
    return ActivityEvent(
        subject_type=SubjectType.BUYER_ROLE,
        event_type=EventType.MATCH_RUN_COMPLETED,
        source=ActivitySource.MATCHING_ENGINE,
        actor=matching_actor(requested_by),
        payload=MatchRunPayload(candidate_count=candidate_count),
        subject_uuid=buyer_role_id,
        outcome=status,
        ledger=LedgerRef(LedgerType.MATCH_RESULT, uuid.UUID(header_row_id)),
        # Status in the key so a FAILED fallback is not dropped after a GENERATED write.
        idempotency_key=f"{EventType.MATCH_RUN_COMPLETED}:{run_id}:{status}",
    )


def decision_event(
    *,
    event_type: EventType,
    match: MatchResultEntity,
    decided_by: str,
    outcome: str,
    deal_attio_id: str | None = None,
) -> ActivityEvent:
    match_result_id = uuid.UUID(match.id)
    return ActivityEvent(
        subject_type=SubjectType.BUYER_ROLE,
        event_type=event_type,
        source=ActivitySource.MATCHING_ENGINE,
        actor=matching_actor(decided_by),
        payload=MatchDecisionPayload(deal_attio_id=deal_attio_id),
        subject_uuid=uuid.UUID(match.buyer_role_id),
        outcome=outcome,
        ledger=LedgerRef(LedgerType.MATCH_RESULT, match_result_id),
        idempotency_key=f"{event_type}:{match_result_id}",
    )
