"""Real-database coverage for the LinkedIn history: one `linkedin_scans` row
per scan, one `signals` row per new item, and one `activities` event pointing
at the scan. Skips cleanly when no database is reachable (see conftest).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Activity, BuyerRole, LinkedInScan, Organization, SellerRole, Signal
from app.modules.enrichment.application.linkedin_history import record_scan
from app.modules.enrichment.domain.linkedin import (
    Contact,
    JobChange,
    LinkedInPost,
    LinkedInProfile,
    ScanRecord,
)
from app.modules.enrichment.domain.linkedin import (
    LinkedInScan as ScanResult,
)
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.persistence.linkedin_unit_of_work import SqlAlchemyLinkedInUnitOfWork

_PROFILE_URL = "https://www.linkedin.com/in/jane-doe"


def _post(post_id: str, *, posted_at: datetime | None = None) -> LinkedInPost:
    return LinkedInPost(
        external_id=post_id,
        url=f"https://www.linkedin.com/posts/{post_id}",
        text="We closed an acquisition in Riyadh",
        author_name="Jane Doe",
        posted_at=posted_at,
    )


def _change() -> JobChange:
    contact = Contact("p1", "Jane Doe", "Acme Co", _PROFILE_URL, "CFO")
    profile = LinkedInProfile(url=_PROFILE_URL, current_title="CFO", current_company="Globex")
    return JobChange(contact, profile, False, True, _PROFILE_URL)


def _post_id() -> str:
    # Signals dedupe on a global (source, external_id): unique per test run.
    return f"test-{uuid.uuid4()}"


async def _record(
    sessionmaker: async_sessionmaker[AsyncSession],
    target: EnrichmentTarget,
    scan: ScanResult,
    *,
    requested_by: str | None = None,
    failure: str | None = None,
) -> ScanResult:
    started = datetime.now(UTC)
    record = ScanRecord(
        target, scan, started, started + timedelta(seconds=2), requested_by, failure
    )
    return await record_scan(lambda: SqlAlchemyLinkedInUnitOfWork(sessionmaker), record)


async def _seller_target(db_session: AsyncSession) -> EnrichmentTarget:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Acme Co")
    db_session.add(org)
    await db_session.flush()
    role = SellerRole(id=uuid.uuid4(), org_attio_id=org.attio_id, is_active=True)
    db_session.add(role)
    await db_session.flush()
    return EnrichmentTarget(EnrichmentTargetKind.SELLER, role.id, org.attio_id, org.name)


async def _scans(db_session: AsyncSession, org_attio_id: str) -> list[LinkedInScan]:
    result = await db_session.execute(
        select(LinkedInScan).where(LinkedInScan.org_attio_id == org_attio_id)
    )
    return list(result.scalars())


async def _signals(db_session: AsyncSession, org_attio_id: str) -> list[Signal]:
    result = await db_session.execute(select(Signal).where(Signal.org_attio_id == org_attio_id))
    return list(result.scalars())


async def _activities(db_session: AsyncSession, org_attio_id: str) -> list[Activity]:
    result = await db_session.execute(
        select(Activity).where(
            Activity.subject_attio_id == org_attio_id,
            Activity.event_type == "linkedin.scan_completed",
        )
    )
    return list(result.scalars())


async def test_a_scan_writes_a_scan_signals_and_one_linked_activity(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)
    scan = ScanResult(
        posts=(_post(_post_id()), _post(_post_id())), job_changes=(_change(),), contacts_scanned=1
    )

    new = await _record(db_sessionmaker, target, scan, requested_by="U123")

    assert len(new.posts) == 2 and len(new.job_changes) == 1
    (row,) = await _scans(db_session, target.org_attio_id)
    assert row.status == "succeeded" and row.error is None
    assert row.seller_role_id == target.role_id and row.buyer_role_id is None
    assert row.requested_by == "U123"
    assert (row.posts_found, row.job_changes_found, row.contacts_scanned) == (2, 1, 1)
    assert row.started_at < row.finished_at
    signals = await _signals(db_session, target.org_attio_id)
    assert len(signals) == 3
    assert {s.linkedin_scan_id for s in signals} == {row.id}
    assert {s.source for s in signals} == {"linkedin"}
    assert {s.tool_run_id for s in signals} == {None}
    (activity,) = await _activities(db_session, target.org_attio_id)
    assert (activity.ledger_type, activity.ledger_id) == ("linkedin_scan", row.id)
    assert activity.actor_type == "slack_user" and activity.actor_ref == "U123"
    assert activity.source == "enrichment" and activity.subject_type == "Organization"
    assert activity.payload == {
        "kind": "linkedin_scan",
        "new_posts": 2,
        "new_job_changes": 1,
        "contacts_scanned": 1,
        "contacts_without_linkedin": 0,
    }


async def test_activity_payload_never_holds_names_or_post_text(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)
    scan = ScanResult(posts=(_post(_post_id()),), job_changes=(_change(),))

    await _record(db_sessionmaker, target, scan)

    (activity,) = await _activities(db_session, target.org_attio_id)
    dumped = str(activity.payload)
    assert "Jane" not in dumped and "acquisition" not in dumped and "Globex" not in dumped


async def test_a_second_identical_scan_stores_nothing_new(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)
    scan = ScanResult(posts=(_post(_post_id()),), job_changes=(_change(),))

    await _record(db_sessionmaker, target, scan)
    again = await _record(db_sessionmaker, target, scan)

    assert again.posts == () and again.job_changes == ()
    assert len(await _signals(db_session, target.org_attio_id)) == 2
    # Every run is history, new items or not: a scan row and an activity each time.
    assert len(await _scans(db_session, target.org_attio_id)) == 2
    activities = await _activities(db_session, target.org_attio_id)
    assert sorted(a.payload["new_posts"] for a in activities) == [0, 1]


async def test_a_post_seen_twice_in_one_scan_is_stored_once(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)
    post = _post(_post_id())

    new = await _record(db_sessionmaker, target, ScanResult(posts=(post, post)))

    assert len(new.posts) == 1
    assert len(await _signals(db_session, target.org_attio_id)) == 1
    (row,) = await _scans(db_session, target.org_attio_id)
    assert row.posts_found == 1


async def test_a_post_without_a_date_is_stored_with_the_scan_time(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)

    await _record(db_sessionmaker, target, ScanResult(posts=(_post(_post_id(), posted_at=None),)))

    (signal,) = await _signals(db_session, target.org_attio_id)
    assert (datetime.now(UTC) - signal.ts).total_seconds() < 60


async def test_a_scan_with_nothing_found_still_stores_the_scan_and_an_activity(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)

    await _record(db_sessionmaker, target, ScanResult(contacts_scanned=2))

    (row,) = await _scans(db_session, target.org_attio_id)
    (activity,) = await _activities(db_session, target.org_attio_id)
    assert (activity.ledger_type, activity.ledger_id) == ("linkedin_scan", row.id)
    assert activity.outcome == "succeeded"
    assert activity.payload["new_posts"] == 0 and activity.payload["contacts_scanned"] == 2
    assert await _signals(db_session, target.org_attio_id) == []


async def test_no_triggering_user_falls_back_to_the_system_actor(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)

    await _record(db_sessionmaker, target, ScanResult())

    (activity,) = await _activities(db_session, target.org_attio_id)
    assert activity.actor_type == "system" and activity.actor_ref == "enrichment"
    (row,) = await _scans(db_session, target.org_attio_id)
    assert row.requested_by is None


async def test_a_failed_scan_is_stored_as_a_failed_scan_and_activity(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)

    result = await _record(
        db_sessionmaker, target, ScanResult(), requested_by="U123", failure="TimeoutError"
    )

    assert result.is_empty
    (row,) = await _scans(db_session, target.org_attio_id)
    assert row.status == "failed" and row.error == "TimeoutError"
    (activity,) = await _activities(db_session, target.org_attio_id)
    assert activity.outcome == "failed"
    assert (activity.ledger_type, activity.ledger_id) == ("linkedin_scan", row.id)
    assert await _signals(db_session, target.org_attio_id) == []


async def test_a_buyer_scan_links_the_buyer_role(db_session: AsyncSession, db_sessionmaker) -> None:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Acme Capital")
    db_session.add(org)
    await db_session.flush()
    role = BuyerRole(id=uuid.uuid4(), org_attio_id=org.attio_id, is_active=True)
    db_session.add(role)
    await db_session.flush()
    target = EnrichmentTarget(EnrichmentTargetKind.BUYER, role.id, org.attio_id, org.name)

    await _record(db_sessionmaker, target, ScanResult(posts=(_post(_post_id()),)))

    (row,) = await _scans(db_session, org.attio_id)
    assert row.buyer_role_id == role.id and row.seller_role_id is None
    assert len(await _signals(db_session, org.attio_id)) == 1


async def test_signal_payloads_are_typed_by_kind(db_session: AsyncSession, db_sessionmaker) -> None:
    target = await _seller_target(db_session)

    await _record(
        db_sessionmaker, target, ScanResult(posts=(_post(_post_id()),), job_changes=(_change(),))
    )

    kinds = {s.payload["kind"] for s in await _signals(db_session, target.org_attio_id)}
    assert kinds == {"post", "job_change"}


async def test_deleting_the_organization_removes_its_scans_and_signals(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)
    await _record(db_sessionmaker, target, ScanResult(posts=(_post(_post_id()),)))
    # The seller role references the organization with no cascade; clear it first.
    await db_session.execute(text("DELETE FROM seller_roles WHERE id = :r"), {"r": target.role_id})

    await db_session.execute(
        text("DELETE FROM organizations WHERE attio_id = :o"), {"o": target.org_attio_id}
    )

    assert await _scans(db_session, target.org_attio_id) == []
    assert await _signals(db_session, target.org_attio_id) == []


async def test_deleting_the_role_keeps_the_scan_with_the_role_nulled(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)
    await _record(db_sessionmaker, target, ScanResult())

    await db_session.execute(text("DELETE FROM seller_roles WHERE id = :r"), {"r": target.role_id})

    (row,) = await _scans(db_session, target.org_attio_id)
    await db_session.refresh(row)
    assert row.seller_role_id is None
