"""Real-database coverage for `SqlAlchemyLinkedInHistory`: one `tool_runs`
row per scan, one `signals` row per new item, one `activities` event for a
scan that found something new. Skips cleanly when no database is reachable.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Activity, BuyerRole, Organization, SellerRole, Signal, ToolRun
from app.modules.enrichment.domain.linkedin import (
    Contact,
    JobChange,
    LinkedInPost,
    LinkedInProfile,
    LinkedInScan,
)
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.persistence.linkedin_history import SqlAlchemyLinkedInHistory

_PROFILE_URL = "https://www.linkedin.com/in/jane-doe"


def _post(post_id: str = "1", *, posted_at: datetime | None = None) -> LinkedInPost:
    return LinkedInPost(
        external_id=post_id,
        url=f"https://www.linkedin.com/posts/{post_id}",
        text="We closed an acquisition in Riyadh",
        author_name="Jane Doe",
        posted_at=posted_at,
    )


def _change() -> JobChange:
    contact = Contact(
        person_attio_id="p1",
        name="Jane Doe",
        company_name="Acme Co",
        linkedin_url=_PROFILE_URL,
        job_title="CFO",
    )
    profile = LinkedInProfile(url=_PROFILE_URL, current_title="CFO", current_company="Globex")
    return JobChange(
        contact=contact,
        profile=profile,
        title_changed=False,
        company_changed=True,
        source_url=_PROFILE_URL,
    )


def _post_id() -> str:
    # Signals dedupe on a global (source, external_id): unique per test run.
    return f"test-{uuid.uuid4()}"


async def _seller_target(db_session: AsyncSession) -> EnrichmentTarget:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Acme Co")
    db_session.add(org)
    await db_session.flush()
    role = SellerRole(id=uuid.uuid4(), org_attio_id=org.attio_id, is_active=True)
    db_session.add(role)
    await db_session.flush()
    return EnrichmentTarget(EnrichmentTargetKind.SELLER, role.id, org.attio_id, org.name)


async def _signals(db_session: AsyncSession, org_attio_id: str) -> list[Signal]:
    result = await db_session.execute(select(Signal).where(Signal.org_attio_id == org_attio_id))
    return list(result.scalars())


async def _runs(db_session: AsyncSession, org_attio_id: str) -> list[ToolRun]:
    result = await db_session.execute(
        select(ToolRun).where(ToolRun.organization_attio_id == org_attio_id)
    )
    return list(result.scalars())


async def _activities(db_session: AsyncSession, org_attio_id: str) -> list[Activity]:
    result = await db_session.execute(
        select(Activity).where(
            Activity.subject_attio_id == org_attio_id,
            Activity.event_type == "linkedin.scan_completed",
        )
    )
    return list(result.scalars())


async def test_a_scan_writes_a_run_signals_and_one_linked_activity(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)
    scan = LinkedInScan(
        posts=(_post(_post_id()), _post(_post_id())),
        job_changes=(_change(),),
        contacts_scanned=1,
    )

    new = await SqlAlchemyLinkedInHistory(db_sessionmaker).record(target, scan)

    assert len(new.posts) == 2 and len(new.job_changes) == 1
    runs = await _runs(db_session, target.org_attio_id)
    assert len(runs) == 1
    assert runs[0].tool == "linkedin_scan" and runs[0].status == "succeeded"
    assert runs[0].seller_role_id == target.role_id and runs[0].buyer_role_id is None
    signals = await _signals(db_session, target.org_attio_id)
    assert len(signals) == 3
    assert {s.tool_run_id for s in signals} == {runs[0].id}
    assert {s.source for s in signals} == {"linkedin"}
    activities = await _activities(db_session, target.org_attio_id)
    assert len(activities) == 1
    activity = activities[0]
    assert (activity.ledger_type, activity.ledger_id) == ("tool_run", runs[0].id)
    assert activity.actor_type == "system" and activity.source == "enrichment"
    assert activity.subject_type == "Organization"
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
    await SqlAlchemyLinkedInHistory(db_sessionmaker).record(
        target, LinkedInScan(posts=(_post(_post_id()),), job_changes=(_change(),))
    )

    (activity,) = await _activities(db_session, target.org_attio_id)

    dumped = str(activity.payload)
    assert "Jane" not in dumped and "acquisition" not in dumped and "Globex" not in dumped


async def test_a_second_identical_scan_stores_nothing_new(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)
    scan = LinkedInScan(posts=(_post(_post_id()),), job_changes=(_change(),))
    history = SqlAlchemyLinkedInHistory(db_sessionmaker)

    await history.record(target, scan)
    again = await history.record(target, scan)

    assert again.posts == () and again.job_changes == ()
    assert len(await _signals(db_session, target.org_attio_id)) == 2
    # Every run is history, new items or not: a run row and an activity each time.
    assert len(await _runs(db_session, target.org_attio_id)) == 2
    activities = await _activities(db_session, target.org_attio_id)
    assert len(activities) == 2
    assert sorted(a.payload["new_posts"] for a in activities) == [0, 1]


async def test_a_post_seen_twice_in_one_scan_is_stored_once(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)
    post = _post(_post_id())

    new = await SqlAlchemyLinkedInHistory(db_sessionmaker).record(
        target, LinkedInScan(posts=(post, post))
    )

    assert len(new.posts) == 1
    assert len(await _signals(db_session, target.org_attio_id)) == 1


async def test_a_post_without_a_date_is_stored_with_the_write_time(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)

    await SqlAlchemyLinkedInHistory(db_sessionmaker).record(
        target, LinkedInScan(posts=(_post(_post_id(), posted_at=None),))
    )

    (signal,) = await _signals(db_session, target.org_attio_id)
    assert signal.ts is not None
    assert (datetime.now(UTC) - signal.ts).total_seconds() < 60


async def test_a_scan_with_nothing_found_still_logs_the_run_and_an_activity(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)

    await SqlAlchemyLinkedInHistory(db_sessionmaker).record(
        target, LinkedInScan(contacts_scanned=2)
    )

    (run,) = await _runs(db_session, target.org_attio_id)
    (activity,) = await _activities(db_session, target.org_attio_id)
    assert (activity.ledger_type, activity.ledger_id) == ("tool_run", run.id)
    assert activity.outcome == "succeeded"
    assert activity.payload["new_posts"] == 0 and activity.payload["contacts_scanned"] == 2
    assert await _signals(db_session, target.org_attio_id) == []


async def test_the_slack_user_who_triggered_the_scan_is_the_actor(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)

    await SqlAlchemyLinkedInHistory(db_sessionmaker).record(
        target, LinkedInScan(), requested_by="U123"
    )

    (activity,) = await _activities(db_session, target.org_attio_id)
    assert activity.actor_type == "slack_user" and activity.actor_ref == "U123"


async def test_no_triggering_user_falls_back_to_the_system_actor(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)

    await SqlAlchemyLinkedInHistory(db_sessionmaker).record(target, LinkedInScan())

    (activity,) = await _activities(db_session, target.org_attio_id)
    assert activity.actor_type == "system" and activity.actor_ref == "enrichment"


async def test_a_failed_scan_is_stored_as_a_failed_run_and_activity(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    target = await _seller_target(db_session)

    result = await SqlAlchemyLinkedInHistory(db_sessionmaker).record(
        target, LinkedInScan(), requested_by="U123", failure="TimeoutError"
    )

    assert result.is_empty
    (run,) = await _runs(db_session, target.org_attio_id)
    assert run.status == "failed" and run.error == "TimeoutError"
    (activity,) = await _activities(db_session, target.org_attio_id)
    assert activity.outcome == "failed"
    assert (activity.ledger_type, activity.ledger_id) == ("tool_run", run.id)
    assert activity.actor_ref == "U123"
    assert await _signals(db_session, target.org_attio_id) == []


async def test_a_buyer_scan_links_the_buyer_role(db_session: AsyncSession, db_sessionmaker) -> None:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Acme Capital")
    db_session.add(org)
    await db_session.flush()
    role = BuyerRole(id=uuid.uuid4(), org_attio_id=org.attio_id, is_active=True)
    db_session.add(role)
    await db_session.flush()
    target = EnrichmentTarget(EnrichmentTargetKind.BUYER, role.id, org.attio_id, org.name)

    await SqlAlchemyLinkedInHistory(db_sessionmaker).record(
        target, LinkedInScan(posts=(_post(_post_id()),))
    )

    (run,) = await _runs(db_session, org.attio_id)
    assert run.buyer_role_id == role.id and run.seller_role_id is None
    assert len(await _signals(db_session, org.attio_id)) == 1


async def test_signal_payloads_are_typed_by_kind(db_session: AsyncSession, db_sessionmaker) -> None:
    target = await _seller_target(db_session)
    await SqlAlchemyLinkedInHistory(db_sessionmaker).record(
        target, LinkedInScan(posts=(_post(_post_id()),), job_changes=(_change(),))
    )

    kinds = {s.payload["kind"] for s in await _signals(db_session, target.org_attio_id)}

    assert kinds == {"post", "job_change"}
    count = await db_session.scalar(select(func.count()).select_from(Signal))
    assert count is not None and count >= 2
