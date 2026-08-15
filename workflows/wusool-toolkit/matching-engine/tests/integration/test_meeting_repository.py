from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.buyers.application.resolution_service import BuyerResolutionService
from app.modules.buyers.infrastructure.repositories import BuyerRepository
from app.modules.matching.infrastructure.meeting_repository import MeetingRepository


async def test_get_recent_by_org_returns_notes_ordered_by_occurred_at_desc(
    db_session: AsyncSession, org_with_meetings
) -> None:
    org, _meetings = org_with_meetings
    repo = MeetingRepository(db_session, max_chars=600)

    notes = await repo.get_recent_by_org(org.attio_id)

    assert len(notes) == 3
    assert [n.occurred_at.day for n in notes] == [28, 20, 10]


async def test_get_recent_by_org_truncates_long_summaries(
    db_session: AsyncSession, org_with_meetings
) -> None:
    org, _meetings = org_with_meetings
    repo = MeetingRepository(db_session, max_chars=10)

    notes = await repo.get_recent_by_org(org.attio_id)

    assert all(note.truncated for note in notes)
    assert all(note.summary.endswith("... [truncated]") for note in notes)


async def test_get_recent_by_org_returns_empty_list_for_org_with_no_meetings(
    db_session: AsyncSession,
) -> None:
    repo = MeetingRepository(db_session, max_chars=600)

    notes = await repo.get_recent_by_org("no-such-org-id")

    assert notes == []


async def test_resolve_by_id_populates_buyer_context_meeting_notes(
    db_session: AsyncSession, org_with_meetings, any_buyer_role
) -> None:
    org, _meetings = org_with_meetings
    any_buyer_role.org_attio_id = org.attio_id
    await db_session.flush()

    meetings = MeetingRepository(db_session, max_chars=600)
    service = BuyerResolutionService(BuyerRepository(db_session), meetings)

    context = await service.resolve_by_id(str(any_buyer_role.id))

    assert context is not None
    assert len(context.meeting_notes) == 3
    assert context.meeting_notes[0].occurred_at.day == 28
