"""`try_advisory_lock` when the connection holding the lock fails. Fakes stand in for the
engine, since a real connection can't be made to die at exactly the right moment."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import Select

from app.modules.interactions.persistence.advisory_lock import try_advisory_lock


class _Result:
    def __init__(self, value: bool) -> None:
        self._value = value

    def scalar_one(self) -> bool:
        return self._value


class _Connection:
    """The first statement takes the lock; the second releases it, and can be made to fail."""

    def __init__(self, *, wins: bool = True, unlock_fails: bool = False) -> None:
        self.statements = 0
        self.invalidated = False
        self._wins = wins
        self._unlock_fails = unlock_fails

    async def execution_options(self, **options: str) -> "_Connection":
        return self

    async def invalidate(self) -> None:
        self.invalidated = True

    async def execute(self, statement: Select[tuple[bool]]) -> _Result:
        self.statements += 1
        if self.statements == 1:
            return _Result(self._wins)
        if self._unlock_fails:
            raise RuntimeError("connection lost")
        return _Result(True)


class _Engine:
    def __init__(self, connection: _Connection) -> None:
        self._connection = connection

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[_Connection]:
        yield self._connection


async def test_a_failed_release_does_not_raise_when_the_block_succeeded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = _Connection(unlock_fails=True)

    with caplog.at_level(logging.WARNING):
        async with try_advisory_lock(_Engine(connection), 1) as won:  # type: ignore[arg-type]
            assert won

    assert "interactions_lock_release_failed" in caplog.text


async def test_a_failed_release_never_hides_the_blocks_own_error() -> None:
    connection = _Connection(unlock_fails=True)

    with pytest.raises(ValueError, match="pass failed"):
        async with try_advisory_lock(_Engine(connection), 1):  # type: ignore[arg-type]
            raise ValueError("pass failed")


async def test_a_lock_that_was_not_won_is_never_released() -> None:
    connection = _Connection(wins=False)

    async with try_advisory_lock(_Engine(connection), 1) as won:  # type: ignore[arg-type]
        assert not won

    assert connection.statements == 1


async def test_a_failed_release_closes_the_connection_so_the_lock_cannot_leak() -> None:
    connection = _Connection(unlock_fails=True)

    async with try_advisory_lock(_Engine(connection), 1):  # type: ignore[arg-type]
        pass

    assert connection.invalidated


async def test_a_clean_release_keeps_the_connection() -> None:
    connection = _Connection()

    async with try_advisory_lock(_Engine(connection), 1):  # type: ignore[arg-type]
        pass

    assert not connection.invalidated
