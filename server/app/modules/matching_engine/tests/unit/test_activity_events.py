import uuid

from app.modules.activities import EventType, LedgerType
from app.modules.matching_engine.application.activity_events import run_completed_event


def _event(status: str):
    return run_completed_event(
        run_id=RUN_ID,
        header_row_id=str(uuid.uuid4()),
        buyer_role_id=uuid.uuid4(),
        requested_by="U1",
        status=status,
        candidate_count=3,
    )


RUN_ID = uuid.uuid4()


def test_a_run_event_links_the_header_row_and_names_the_outcome() -> None:
    event = _event("GENERATED")

    assert event.event_type is EventType.MATCH_RUN_COMPLETED
    assert event.ledger is not None and event.ledger.type is LedgerType.MATCH_RESULT
    assert event.outcome == "GENERATED"


def test_a_failed_fallback_is_not_dropped_after_a_generated_write() -> None:
    """Both can happen when something raises after `_run` committed; each must record."""
    assert _event("GENERATED").idempotency_key != _event("FAILED").idempotency_key
