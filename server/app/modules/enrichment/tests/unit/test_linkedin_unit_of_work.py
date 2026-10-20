"""`SqlAlchemyLinkedInUnitOfWork`'s own contract with a fake session: commit on
clean exit, rollback on exception. Mirrors `ddl_commands`' unit-of-work test.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.enrichment.persistence.linkedin_unit_of_work import SqlAlchemyLinkedInUnitOfWork


def _fake_session() -> AsyncMock:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False
    return session


async def test_commits_on_clean_exit() -> None:
    session = _fake_session()

    async with SqlAlchemyLinkedInUnitOfWork(MagicMock(return_value=session)):
        pass

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


async def test_rolls_back_on_exception() -> None:
    session = _fake_session()

    with pytest.raises(ValueError):
        async with SqlAlchemyLinkedInUnitOfWork(MagicMock(return_value=session)):
            raise ValueError("boom")

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


async def test_exposes_repositories_bound_to_the_session() -> None:
    session = _fake_session()

    async with SqlAlchemyLinkedInUnitOfWork(MagicMock(return_value=session)) as uow:
        assert uow.scans is not None
        assert uow.signals is not None
        assert uow.activities is not None
