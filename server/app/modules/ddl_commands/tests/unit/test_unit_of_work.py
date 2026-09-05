"""Verifies `SqlAlchemyDdlCommandsUnitOfWork`'s own contract directly (commit
on clean exit, rollback on exception) with a fake session — mirrors
`matching_engine`'s own `test_unit_of_work.py`.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.ddl_commands.persistence.unit_of_work import SqlAlchemyDdlCommandsUnitOfWork


def _fake_sessionmaker(session: AsyncMock):
    return MagicMock(return_value=session)


def _fake_session() -> AsyncMock:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False
    return session


async def test_commits_on_clean_exit() -> None:
    session = _fake_session()
    uow = SqlAlchemyDdlCommandsUnitOfWork(_fake_sessionmaker(session))

    async with uow:
        pass

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


async def test_rolls_back_on_exception() -> None:
    session = _fake_session()
    uow = SqlAlchemyDdlCommandsUnitOfWork(_fake_sessionmaker(session))

    with pytest.raises(ValueError):
        async with uow:
            raise ValueError("boom")

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


async def test_exposes_repositories_bound_to_the_session() -> None:
    session = _fake_session()
    uow = SqlAlchemyDdlCommandsUnitOfWork(_fake_sessionmaker(session))

    async with uow as entered:
        assert entered.buyers is not None
        assert entered.sellers is not None
        assert entered.organizations is not None
