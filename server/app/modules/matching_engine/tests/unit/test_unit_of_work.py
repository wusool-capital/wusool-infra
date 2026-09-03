"""Verifies `SqlAlchemyMatchingUnitOfWork`'s own contract directly (commit on
clean exit, rollback on exception) with a fake session — the repositories'
own read/write behavior is already covered by their own repository tests;
this is only about the transaction-boundary semantics the UoW itself owns.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.matching_engine.persistence.unit_of_work import SqlAlchemyMatchingUnitOfWork


def _fake_sessionmaker(session: AsyncMock):
    return MagicMock(return_value=session)


def _fake_session() -> AsyncMock:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False
    return session


async def test_commits_on_clean_exit() -> None:
    session = _fake_session()
    uow = SqlAlchemyMatchingUnitOfWork(_fake_sessionmaker(session))

    async with uow:
        pass

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


async def test_rolls_back_on_exception() -> None:
    session = _fake_session()
    uow = SqlAlchemyMatchingUnitOfWork(_fake_sessionmaker(session))

    with pytest.raises(ValueError):
        async with uow:
            raise ValueError("boom")

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


async def test_exposes_repositories_bound_to_the_session() -> None:
    session = _fake_session()
    uow = SqlAlchemyMatchingUnitOfWork(_fake_sessionmaker(session))

    async with uow as entered:
        assert entered.match_results is not None
        assert entered.match_scores is not None
        assert entered.meetings is not None
