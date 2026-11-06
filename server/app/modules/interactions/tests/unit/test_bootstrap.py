"""The poll loop's behaviour. A failed pass must not kill it, cancellation (how `main.py` stops
it on shutdown) must propagate, and it must stay off unless it is switched on and configured."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.modules.google_workspace import (
    CALENDAR_READONLY,
    GMAIL_READONLY,
    CalendarSourcePort,
    GoogleWorkspaceSettings,
    MailSourcePort,
    ServiceAccountKey,
)
from app.modules.interactions import bootstrap
from app.modules.interactions.application.ingest import IngestConfig, PassReport
from app.modules.interactions.application.ports.interaction_store import InteractionStorePort
from app.modules.interactions.application.ports.record_directory import RecordDirectoryPort
from app.modules.interactions.bootstrap import LOCK_KEY, LockFactory, PassRunner, run_loop
from app.modules.interactions.config import InteractionsSettings

START = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
INTERVAL_S = 3600
KEY_JSON = (
    '{"client_email": "reader@proj.iam.gserviceaccount.com",'
    ' "private_key": "pem", "private_key_id": "kid-1"}'
)


class _Service:
    def __init__(self, *, failing_passes: int = 0, failing_purges: int = 0) -> None:
        self.passes = 0
        self.purges = 0
        self._failing_passes = failing_passes
        self._failing_purges = failing_purges

    async def run_pass(self) -> PassReport:
        self.passes += 1
        if self.passes <= self._failing_passes:
            raise RuntimeError("boom")
        return PassReport(0, 0, 0, 0, ())

    async def purge_expired(self) -> int:
        self.purges += 1
        if self.purges <= self._failing_purges:
            raise RuntimeError("purge failed")
        return 3


class _Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


class _Sleeper:
    """Advances the fake clock by what was asked, and stops the loop after `stop_after` sleeps."""

    def __init__(self, clock: _Clock, stop_after: int) -> None:
        self.calls: list[float] = []
        self._clock = clock
        self._stop_after = stop_after

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        self._clock.now += timedelta(seconds=seconds)
        if len(self.calls) >= self._stop_after:
            raise asyncio.CancelledError


def _locks(*results: bool) -> LockFactory:
    """Yields the scripted outcomes in order, then wins every time."""
    queue = list(results)

    @asynccontextmanager
    async def lock() -> AsyncIterator[bool]:
        yield queue.pop(0) if queue else True

    return lock


async def _run(service: _Service, lock: LockFactory, passes: int) -> _Sleeper:
    clock = _Clock()
    sleeper = _Sleeper(clock, stop_after=passes)
    with pytest.raises(asyncio.CancelledError):
        await run_loop(service, lock, INTERVAL_S, clock, sleeper)
    return sleeper


async def test_each_round_runs_a_pass_then_waits_the_interval() -> None:
    service = _Service()

    sleeper = await _run(service, _locks(), passes=3)

    assert service.passes == 3
    assert sleeper.calls == [INTERVAL_S] * 3


async def test_a_round_that_loses_the_lock_runs_nothing_and_the_loop_carries_on() -> None:
    service = _Service()

    await _run(service, _locks(False, False, True), passes=3)

    assert service.passes == 1


async def test_a_failed_pass_is_logged_and_the_loop_keeps_going(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = _Service(failing_passes=1)

    with caplog.at_level(logging.ERROR):
        await _run(service, _locks(), passes=3)

    assert service.passes == 3
    assert "interactions_pass_failed" in caplog.text


async def test_cancellation_inside_a_pass_is_not_swallowed() -> None:
    class _Cancelled(_Service):
        async def run_pass(self) -> PassReport:
            raise asyncio.CancelledError

    clock = _Clock()
    with pytest.raises(asyncio.CancelledError):
        await run_loop(_Cancelled(), _locks(), INTERVAL_S, clock, _Sleeper(clock, stop_after=99))


async def test_expired_rows_are_purged_on_the_first_pass_then_once_a_day() -> None:
    service = _Service()

    # Hourly passes: the first purges, the 25th is a day later and purges again.
    await _run(service, _locks(), passes=26)

    assert service.passes == 26
    assert service.purges == 2


async def test_a_failed_purge_is_retried_on_the_next_pass() -> None:
    service = _Service(failing_purges=1)

    await _run(service, _locks(), passes=3)

    assert service.purges == 2


async def test_the_purge_only_runs_while_the_lock_is_held() -> None:
    service = _Service()

    await _run(service, _locks(False, False), passes=2)

    assert service.purges == 0


def test_the_lock_key_fits_in_a_signed_bigint() -> None:
    assert 0 < LOCK_KEY < 2**63


async def test_the_loop_stays_off_unless_it_is_switched_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode() -> None:
        raise AssertionError("must not touch the database while disabled")

    monkeypatch.setattr(
        bootstrap, "get_settings", lambda: InteractionsSettings(interactions_enabled=False)
    )
    monkeypatch.setattr(bootstrap, "get_sessionmaker", explode)
    monkeypatch.setattr(bootstrap, "get_engine", explode)

    await bootstrap.run_interactions_forever()


async def test_enabled_without_a_google_key_does_not_start(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        bootstrap, "get_settings", lambda: InteractionsSettings(interactions_enabled=True)
    )
    monkeypatch.setattr(
        bootstrap,
        "get_google_settings",
        lambda: GoogleWorkspaceSettings(google_service_account_json=None),
    )

    with caplog.at_level(logging.ERROR):
        await bootstrap.run_interactions_forever()

    assert "GOOGLE_SERVICE_ACCOUNT_JSON is not set" in caplog.text


async def test_a_malformed_key_does_not_start_and_is_never_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        bootstrap, "get_settings", lambda: InteractionsSettings(interactions_enabled=True)
    )
    monkeypatch.setattr(
        bootstrap,
        "get_google_settings",
        lambda: GoogleWorkspaceSettings(
            google_service_account_json='{"private_key": "SECRET-PEM"}'
        ),
    )

    with caplog.at_level(logging.ERROR):
        await bootstrap.run_interactions_forever()

    assert "GOOGLE_SERVICE_ACCOUNT_JSON is not valid" in caplog.text
    assert "SECRET-PEM" not in caplog.text


@dataclass
class _Seen:
    """What the wiring handed to its collaborators."""

    scopes: tuple[str, ...] = ()
    config: IngestConfig | None = None
    interval_s: float | None = None
    lock_engine_id: int | None = None
    lock_key: int | None = None


async def test_the_enabled_loop_asks_for_both_scopes_and_runs_under_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _Seen()

    class _Tokens:
        def __init__(
            self, key: ServiceAccountKey, http: httpx.AsyncClient, scopes: tuple[str, ...]
        ) -> None:
            seen.scopes = scopes

    class _Ingest:
        def __init__(
            self,
            store: InteractionStorePort,
            directory: RecordDirectoryPort,
            mail: MailSourcePort,
            calendar: CalendarSourcePort,
            config: IngestConfig,
        ) -> None:
            seen.config = config

    async def fake_run_loop(service: PassRunner, lock: LockFactory, interval_s: float) -> None:
        seen.interval_s = interval_s
        async with lock():
            pass

    @asynccontextmanager
    async def fake_lock(engine: AsyncEngine, key: int) -> AsyncIterator[bool]:
        seen.lock_engine_id, seen.lock_key = id(engine), key
        yield True

    engine = object()
    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: InteractionsSettings(
            interactions_enabled=True,
            interactions_poll_interval_s=60,
            interactions_mailboxes="jules@wusoolcapital.com",
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "get_google_settings",
        lambda: GoogleWorkspaceSettings(google_service_account_json=KEY_JSON),
    )
    monkeypatch.setattr(bootstrap, "get_sessionmaker", lambda: object())
    monkeypatch.setattr(bootstrap, "get_engine", lambda: engine)
    monkeypatch.setattr(bootstrap, "DelegatedTokenSource", _Tokens)
    monkeypatch.setattr(bootstrap, "IngestService", _Ingest)
    monkeypatch.setattr(bootstrap, "run_loop", fake_run_loop)
    monkeypatch.setattr(bootstrap, "try_advisory_lock", fake_lock)

    await bootstrap.run_interactions_forever()

    assert seen.scopes == (GMAIL_READONLY, CALENDAR_READONLY)
    assert seen.interval_s == 60
    assert (seen.lock_engine_id, seen.lock_key) == (id(engine), LOCK_KEY)
    assert seen.config is not None
    assert seen.config.mailboxes == ("jules@wusoolcapital.com",)
