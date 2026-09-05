"""Composition glue: request-scoped session/service construction, mirroring
matching_engine's `api/dependencies.py` style — plain functions, `lru_cache`
reserved for true process-lifetime singletons (none needed here yet; the
Bedrock/Attio clients this module's `bootstrap.py` builds are already
cheap, no-arg construction and aren't cached at this layer either, matching
`build_meetings_service`'s own per-call construction of them).
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.meetings.application.service import MeetingsService
from app.modules.meetings.bootstrap import build_meetings_service
from app.modules.meetings.persistence.database import get_sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_meetings_service(session: SessionDep) -> MeetingsService:
    """`session` must stay open for as long as the returned service is in
    use — see `bootstrap.build_meetings_service`'s docstring."""
    return build_meetings_service(session)


MeetingsServiceDep = Annotated[MeetingsService, Depends(get_meetings_service)]
