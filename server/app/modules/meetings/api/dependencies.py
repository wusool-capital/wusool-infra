"""Composition glue: request-scoped session/service construction, mirroring
matching_engine's `api/dependencies.py` style — plain functions, `lru_cache`
reserved for true process-lifetime singletons (none needed here yet; the
Bedrock/Attio clients this module's `bootstrap.py` builds are already
cheap, no-arg construction and aren't cached at this layer either, matching
`build_meetings_service`'s own per-call construction of them).

`get_session` commits on clean exit / rolls back on exception — the same
commit-on-success semantics `matching_engine`'s
`SqlAlchemyMatchingUnitOfWork.__aexit__` gives its own session lifecycle
(see that file's docstring); this module has no Unit-of-Work, so the
FastAPI dependency itself is where that has to happen instead. Without
this, every write this module makes (`session.add`/`flush` only, per
every repository's own docstring) is silently rolled back when the
dependency's `async with` block exits.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.meetings.application.corrections import CorrectionService
from app.modules.meetings.application.service import MeetingsService
from app.modules.meetings.bootstrap import (
    build_correction_service,
    build_feedback_mailer,
    build_feedback_repository,
    build_meetings_service,
)
from app.modules.meetings.persistence.database import get_sessionmaker
from app.modules.meetings.persistence.feedback_repository import FeedbackRepository
from app.modules.notifications import EmailSenderPort


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_meetings_service(session: SessionDep) -> MeetingsService:
    """`session` must stay open for as long as the returned service is in
    use — see `bootstrap.build_meetings_service`'s docstring.

    Do NOT hand this request-scoped service to `BackgroundTasks`: its
    session is committed/closed as soon as this dependency's generator
    resumes (i.e. once the response is on its way), before a scheduled
    background task is guaranteed to run. Use
    `bootstrap.run_summarize_and_publish` for that instead — it opens its
    own session with its own commit/rollback lifecycle.
    """
    return build_meetings_service(session)


MeetingsServiceDep = Annotated[MeetingsService, Depends(get_meetings_service)]


async def get_feedback_repository(session: SessionDep) -> FeedbackRepository:
    return build_feedback_repository(session)


FeedbackRepositoryDep = Annotated[FeedbackRepository, Depends(get_feedback_repository)]


def feedback_mailer() -> EmailSenderPort:
    return build_feedback_mailer()


FeedbackMailerDep = Annotated[EmailSenderPort, Depends(feedback_mailer)]


def get_correction_service() -> CorrectionService:
    return build_correction_service()


CorrectionServiceDep = Annotated[CorrectionService, Depends(get_correction_service)]
