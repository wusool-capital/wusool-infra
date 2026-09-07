"""`NotesRepository`/`MeetingsRepository.set_note_id` against a real
database. Uses `db_session` (conftest.py), so it skips cleanly when no
database is reachable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import BuyerRole, Meeting, Note, Organization
from app.modules.meetings.persistence.meetings_repository import MeetingsRepository
from app.modules.meetings.persistence.notes_repository import NotesRepository


async def _org(session, attio_id: str) -> Organization:
    org = Organization(attio_id=attio_id, name=f"Org {attio_id}")
    session.add(org)
    await session.flush()
    return org


async def _meeting_row(session, *, org_id: str | None = None) -> Meeting:
    meeting = Meeting(
        id=uuid4(),
        org_id=org_id,
        occurred_at=datetime(2026, 9, 7, tzinfo=UTC),
        source="in_house",
        status="completed",
    )
    session.add(meeting)
    await session.flush()
    return meeting


async def test_create_persists_primary_role_and_role_ids_and_returns_id(db_session) -> None:
    org = await _org(db_session, f"org-{uuid4()}")
    buyer_role = BuyerRole(
        id=uuid4(), org_attio_id=org.attio_id, is_active=True, created_at=datetime.now(UTC)
    )
    db_session.add(buyer_role)
    await db_session.flush()

    note_id = await NotesRepository(db_session).create(
        note_id=None,
        organization_id=org.attio_id,
        note_type="Meeting",
        content="Met the founder.",
        primary_role="buyer",
        buyer_role_id=buyer_role.id,
        seller_role_id=None,
    )

    stored = await db_session.get(Note, note_id)
    assert stored is not None
    assert stored.primary_role == "buyer"
    assert stored.organization_id == org.attio_id
    assert stored.buyer_role_id == buyer_role.id


async def test_set_note_id_satisfies_the_new_fk(db_session) -> None:
    org = await _org(db_session, f"org-{uuid4()}")
    meeting = await _meeting_row(db_session, org_id=org.attio_id)
    note_id = await NotesRepository(db_session).create(
        note_id=None,
        organization_id=org.attio_id,
        note_type="Meeting",
        content="Met the founder.",
        primary_role=None,
        buyer_role_id=None,
        seller_role_id=None,
    )

    await MeetingsRepository(db_session).set_note_id(meeting.id, note_id=note_id)
    await db_session.flush()
    # `set_note_id` is a Core UPDATE, not an ORM-tracked change -- the
    # already-loaded `meeting` instance in the identity map needs an
    # explicit refresh to see it.
    await db_session.refresh(meeting)

    assert meeting.note_id == note_id


async def test_failed_insert_leaves_the_outer_transaction_usable(db_session) -> None:
    """Regression test for the savepoint in `NotesRepository.create`: a
    failed flush (here, an FK violation on a nonexistent buyer_role_id)
    must not poison the whole session -- the caller's later statements
    (e.g. `mark_completed`, already run earlier in the real flow) must
    still be committable.
    """
    org = await _org(db_session, f"org-{uuid4()}")

    try:
        await NotesRepository(db_session).create(
            note_id=None,
            organization_id=org.attio_id,
            note_type="Meeting",
            content="Bad row.",
            primary_role=None,
            buyer_role_id=uuid4(),  # no such buyer_roles row -> FK violation
            seller_role_id=None,
        )
    except IntegrityError:
        pass
    else:
        raise AssertionError("expected an IntegrityError from the bad buyer_role_id FK")

    # The session must still be usable -- not left in pending-rollback.
    result = await db_session.execute(
        select(Organization).where(Organization.attio_id == org.attio_id)
    )
    assert result.scalar_one().attio_id == org.attio_id
