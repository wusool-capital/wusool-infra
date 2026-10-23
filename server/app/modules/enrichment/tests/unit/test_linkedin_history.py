"""The history logic (`record_scan`) against an in-memory unit of work: what
is stored, what counts as new, and what the activity says.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.activities import EventType, LedgerType, LinkedInScanPayload, SubjectType
from app.modules.enrichment.application.linkedin_history import record_scan
from app.modules.enrichment.domain.linkedin import (
    Contact,
    JobChange,
    LinkedInPost,
    LinkedInProfile,
    LinkedInScan,
    ScanRecord,
)
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.tests.fakes.linkedin_history import FakeLinkedInHistoryStore

_T0 = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 10, 20, 9, 0, 5, tzinfo=UTC)


@pytest.fixture
def target() -> EnrichmentTarget:
    return EnrichmentTarget(EnrichmentTargetKind.SELLER, uuid.uuid4(), "org-1", "Acme Co")


def _post(post_id: str) -> LinkedInPost:
    return LinkedInPost(external_id=post_id, url=f"https://linkedin.com/posts/{post_id}", text="hi")


def _change() -> JobChange:
    contact = Contact("p1", "Jane Doe", "Acme Co", "https://linkedin.com/in/jane", "CFO")
    profile = LinkedInProfile(
        url="https://linkedin.com/in/jane", current_title="CFO", current_company="Globex"
    )
    return JobChange(contact, profile, False, True, "https://linkedin.com/in/jane")


def _record(
    target: EnrichmentTarget,
    scan: LinkedInScan,
    *,
    requested_by: str | None = None,
    failure: str | None = None,
) -> ScanRecord:
    return ScanRecord(target, scan, _T0, _T1, requested_by=requested_by, failure=failure)


async def test_only_new_posts_and_job_changes_come_back(target: EnrichmentTarget) -> None:
    store = FakeLinkedInHistoryStore()
    scan = LinkedInScan(posts=(_post("1"), _post("2")), job_changes=(_change(),))

    first = await record_scan(store.factory(), _record(target, scan))
    again = await record_scan(store.factory(), _record(target, scan))

    assert len(first.posts) == 2 and len(first.job_changes) == 1
    assert again.posts == () and again.job_changes == ()


async def test_a_post_repeated_within_one_scan_is_stored_once(target: EnrichmentTarget) -> None:
    store = FakeLinkedInHistoryStore()

    new = await record_scan(
        store.factory(), _record(target, LinkedInScan(posts=(_post("1"), _post("1"))))
    )

    assert len(new.posts) == 1
    assert store.scans[0].scan.posts == new.posts  # the stored scan counts it once


async def test_every_scan_is_stored_and_commits(target: EnrichmentTarget) -> None:
    store = FakeLinkedInHistoryStore()
    scan = LinkedInScan(posts=(_post("1"),))

    await record_scan(store.factory(), _record(target, scan))
    await record_scan(store.factory(), _record(target, scan))

    assert len(store.scans) == 2 and store.committed == 2
    assert store.scans[0].started_at < store.scans[0].finished_at


async def test_the_activity_always_points_at_the_scan_with_counts(
    target: EnrichmentTarget,
) -> None:
    store = FakeLinkedInHistoryStore()

    await record_scan(store.factory(), _record(target, LinkedInScan(contacts_scanned=2)))

    (event,) = store.events
    assert event.event_type is EventType.LINKEDIN_SCAN_COMPLETED
    assert event.subject_type is SubjectType.ORGANIZATION
    assert event.subject_attio_id == "org-1"
    assert event.ledger is not None
    assert event.ledger.type is LedgerType.LINKEDIN_SCAN and event.ledger.id == store.scan_ids[0]
    assert event.outcome == "succeeded"
    assert event.idempotency_key == f"linkedin.scan_completed:{store.scan_ids[0]}"
    assert isinstance(event.payload, LinkedInScanPayload)
    assert event.payload.new_posts == 0 and event.payload.contacts_scanned == 2


async def test_the_actor_is_the_slack_user_else_the_system(target: EnrichmentTarget) -> None:
    store = FakeLinkedInHistoryStore()

    await record_scan(store.factory(), _record(target, LinkedInScan(), requested_by="U123"))
    await record_scan(store.factory(), _record(target, LinkedInScan()))

    assert [(e.actor.type.value, e.actor.ref) for e in store.events] == [
        ("slack_user", "U123"),
        ("system", "enrichment"),
    ]


async def test_a_failed_scan_is_stored_with_its_error_type(target: EnrichmentTarget) -> None:
    store = FakeLinkedInHistoryStore()

    result = await record_scan(
        store.factory(),
        _record(target, LinkedInScan(), requested_by="U1", failure="TimeoutError"),
    )

    assert result.is_empty
    assert store.scans[0].failure == "TimeoutError"
    assert store.events[0].outcome == "failed"
    assert store.signal_ids == set()


async def test_a_storage_error_propagates_for_the_caller_to_handle(
    target: EnrichmentTarget,
) -> None:
    store = FakeLinkedInHistoryStore(error=RuntimeError("db down"))

    with pytest.raises(RuntimeError):
        await record_scan(store.factory(), _record(target, LinkedInScan()))
