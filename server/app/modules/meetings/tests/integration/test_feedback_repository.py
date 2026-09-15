"""`FeedbackRepository` against a real database. Uses `db_session`
(conftest.py), so it skips cleanly when no database is reachable.
"""

from uuid import uuid4

from sqlalchemy import select

from app.models import FeedbackSubmission
from app.modules.meetings.persistence.feedback_repository import FeedbackRepository


async def test_create_persists_every_field(db_session) -> None:
    submission_id = uuid4()
    repo = FeedbackRepository(db_session)

    await repo.create(
        id=submission_id,
        category="bug",
        message="Recording button was unresponsive.",
        contact="dev@example.com",
        install_id="install-abc",
        app_version="0.4.8",
        platform="macos 15.6 (aarch64)",
    )

    row = (
        await db_session.execute(
            select(FeedbackSubmission).where(FeedbackSubmission.id == submission_id)
        )
    ).scalar_one()
    assert row.category == "bug"
    assert row.message == "Recording button was unresponsive."
    assert row.contact == "dev@example.com"
    assert row.install_id == "install-abc"
    assert row.app_version == "0.4.8"
    assert row.platform == "macos 15.6 (aarch64)"
    assert row.email_sent is False
    assert row.email_sent_at is None
    assert row.created_at is not None


async def test_create_allows_a_null_contact(db_session) -> None:
    submission_id = uuid4()
    repo = FeedbackRepository(db_session)

    await repo.create(
        id=submission_id,
        category="other",
        message="No particular feedback.",
        contact=None,
        install_id="install-xyz",
        app_version="0.4.8",
        platform="windows x86_64",
    )

    row = (
        await db_session.execute(
            select(FeedbackSubmission).where(FeedbackSubmission.id == submission_id)
        )
    ).scalar_one()
    assert row.contact is None


async def test_mark_email_sent_sets_both_columns(db_session) -> None:
    submission_id = uuid4()
    repo = FeedbackRepository(db_session)
    await repo.create(
        id=submission_id,
        category="feature_request",
        message="Please add dark mode.",
        contact=None,
        install_id="install-abc",
        app_version="0.4.8",
        platform="macos 15.6 (aarch64)",
    )

    await repo.mark_email_sent(id=submission_id)

    row = (
        await db_session.execute(
            select(FeedbackSubmission).where(FeedbackSubmission.id == submission_id)
        )
    ).scalar_one()
    assert row.email_sent is True
    assert row.email_sent_at is not None
