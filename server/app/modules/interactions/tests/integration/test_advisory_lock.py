"""`try_advisory_lock` against a real Postgres: the lock that keeps two instances from
reading the same mailboxes at once."""

import random

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.interactions.config import get_settings
from app.modules.interactions.persistence.advisory_lock import try_advisory_lock
from app.modules.utilities.persistence.engine import get_engine


def _key() -> int:
    """Random, so a test never collides with a real instance holding the production key."""
    return random.randrange(1, 2**62)


async def test_a_second_taker_loses_while_the_first_holds_the_lock(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    engine = get_engine(get_settings().database_url)
    key = _key()

    async with try_advisory_lock(engine, key) as first:
        async with try_advisory_lock(engine, key) as second:
            assert (first, second) == (True, False)


async def test_the_lock_can_be_taken_again_once_it_is_released(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    engine = get_engine(get_settings().database_url)
    key = _key()

    async with try_advisory_lock(engine, key) as first:
        assert first
    async with try_advisory_lock(engine, key) as again:
        assert again


async def test_a_failure_inside_the_block_still_releases_the_lock(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    engine = get_engine(get_settings().database_url)
    key = _key()

    with pytest.raises(RuntimeError):
        async with try_advisory_lock(engine, key) as won:
            assert won
            raise RuntimeError("pass failed")

    async with try_advisory_lock(engine, key) as again:
        assert again


async def test_different_keys_do_not_block_each_other(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    engine = get_engine(get_settings().database_url)

    async with try_advisory_lock(engine, _key()) as first:
        async with try_advisory_lock(engine, _key()) as second:
            assert (first, second) == (True, True)
