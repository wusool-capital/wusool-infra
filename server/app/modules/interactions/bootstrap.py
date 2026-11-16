"""The poll loop: wires the ingest service together and runs it on a timer.

`main.py`'s lifespan starts `run_interactions_forever()` and cancels it on shutdown.
Off by default (`interactions_enabled`): dev and prod share one Google tenant, so only
the instance that is meant to read the mailboxes turns it on.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.modules.attio import attio_is_test, get_attio_client, list_workspace_members
from app.modules.google_workspace import (
    CALENDAR_READONLY,
    GMAIL_READONLY,
    CalendarClient,
    DelegatedTokenSource,
    GmailClient,
)
from app.modules.google_workspace import get_settings as get_google_settings
from app.modules.interactions.application.attio_seed import AttioSeedService, SeedReport
from app.modules.interactions.application.attio_write import (
    AttioWriteConfig,
    AttioWriteService,
    WriteReport,
)
from app.modules.interactions.application.calibration import CalibrationConfig, run_calibration
from app.modules.interactions.application.ingest import IngestConfig, IngestService, PassReport
from app.modules.interactions.config import get_settings
from app.modules.interactions.domain.addresses import team_member_of
from app.modules.interactions.domain.attio_fields import WriteMode
from app.modules.interactions.domain.calibration import CalibrationReport
from app.modules.interactions.persistence.advisory_lock import try_advisory_lock
from app.modules.interactions.persistence.database import get_engine, get_sessionmaker
from app.modules.interactions.persistence.directory import SqlAlchemyRecordDirectory
from app.modules.interactions.persistence.interaction_store import SqlAlchemyInteractionStore
from app.modules.interactions.persistence.score_store import SqlAlchemyScoreStore
from app.modules.interactions.persistence.sent_values import SqlAlchemySentValues
from app.modules.interactions.persistence.touch_reader import SqlAlchemyTouchReader
from app.modules.interactions.providers.attio_companies import AttioStrengthSource
from app.modules.interactions.providers.attio_seed_source import AttioSeedSource
from app.modules.interactions.providers.attio_writer import AttioRecordWriter

logger = logging.getLogger(__name__)

# An arbitrary but fixed key ("interact" as a number), shared by every instance.
LOCK_KEY = int.from_bytes(b"interact", "big")
_PURGE_EVERY = timedelta(hours=24)
_HTTP_TIMEOUT_S = 30.0

LockFactory = Callable[[], AbstractAsyncContextManager[bool]]
Sleep = Callable[[float], Awaitable[None]]


class WriteRunner(Protocol):
    async def run_round(self) -> WriteReport: ...


class PassRunner(Protocol):
    async def run_pass(self) -> PassReport: ...

    async def purge_expired(self) -> int: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def run_loop(
    service: PassRunner,
    lock: LockFactory,
    interval_s: float,
    clock: Callable[[], datetime] = _utc_now,
    sleep: Sleep = asyncio.sleep,
    attio_write: WriteRunner | None = None,
) -> None:
    """One pass every `interval_s`, under the lock. A failed pass is logged and never stops
    the loop: a stuck mailbox matters far less than the loop dying silently."""
    last_purge: datetime | None = None
    while True:
        try:
            async with lock() as won:
                if won:
                    last_purge = await _round(service, clock, last_purge, attio_write)
                else:
                    logger.info("interactions_pass_skipped: another instance holds the lock")
        except asyncio.CancelledError:
            raise
        except Exception:
            # Reaching here means the lock itself failed; the round's own failures are handled.
            logger.exception("interactions_pass_failed")
        await sleep(interval_s)


async def _round(
    service: PassRunner,
    clock: Callable[[], datetime],
    last_purge: datetime | None,
    attio_write: WriteRunner | None = None,
) -> datetime | None:
    """One pass, the Attio write, then the daily purge. Each is guarded alone, so none can
    skip another."""
    try:
        await service.run_pass()
    except Exception:
        logger.exception("interactions_pass_failed")
    if attio_write is not None:
        await _write_round(attio_write)
    now = clock()
    if last_purge is not None and now - last_purge < _PURGE_EVERY:
        return last_purge
    try:
        purged = await service.purge_expired()
    except Exception:
        logger.exception("interactions_purge_failed")
        return last_purge  # unchanged, so the next round tries again
    logger.info("interactions_purged rows=%d", purged)
    return now


async def _write_round(attio_write: WriteRunner) -> None:
    try:
        report = await attio_write.run_round()
    except Exception:
        logger.exception("interactions_attio_write_round_failed")
        return
    logger.info(
        "interactions_attio_write patched=%d fields=%d cleared=%d failed=%d "
        "scores_updated=%d unseeded=%d hit_cap=%s dry_run=%s",
        report.patched,
        report.fields,
        report.cleared,
        report.failed,
        report.scores_updated,
        len(report.unseeded),
        report.hit_cap,
        report.dry_run,
    )
    # The stale-sync alarm watches this line. A round counts as moving unless every attempt
    # failed, so one bad record cannot keep the alarm on; failures are logged above.
    if not report.dry_run and not report.unseeded and (report.failed == 0 or report.patched > 0):
        logger.info("interactions_attio_sync_ok")


async def run_interactions_forever() -> None:
    """Never raises except to be cancelled. `main.py` awaits this task at shutdown, and a
    startup failure must not become an error there that skips the rest of shutdown."""
    try:
        await _start()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("interactions_stopped: could not start or keep running")


async def _start() -> None:
    settings = get_settings()
    if not settings.interactions_enabled:
        logger.info("interactions_disabled: set INTERACTIONS_ENABLED=true to start the loop")
        return
    try:
        key = get_google_settings().service_account_key()
    except ValidationError:
        # The message is deliberately generic: the error text must never carry key material.
        logger.error("interactions_not_started: GOOGLE_SERVICE_ACCOUNT_JSON is not valid")
        return
    if key is None:
        logger.error("interactions_not_started: GOOGLE_SERVICE_ACCOUNT_JSON is not set")
        return

    sessionmaker = get_sessionmaker()
    engine = get_engine()
    config = IngestConfig(
        mailboxes=settings.mailboxes,
        internal_domains=settings.internal_domains,
        backfill_months=settings.interactions_backfill_months,
        retention_months=settings.interactions_retention_months,
        next_window_days=settings.interactions_next_window_days,
    )
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as http:
        try:
            tokens = DelegatedTokenSource(key, http, (GMAIL_READONLY, CALENDAR_READONLY))
        except ValueError:
            # Generic on purpose, like the check above: never echo anything from the key.
            logger.error("interactions_not_started: the service-account private key can't be read")
            return
        service = IngestService(
            SqlAlchemyInteractionStore(sessionmaker),
            SqlAlchemyRecordDirectory(sessionmaker),
            GmailClient(http, tokens),
            CalendarClient(http, tokens),
            config,
        )
        async with _attio_write_runner() as attio_write:
            await run_loop(
                service,
                lambda: try_advisory_lock(engine, LOCK_KEY),
                settings.interactions_poll_interval_s,
                attio_write=attio_write,
            )


@asynccontextmanager
async def _attio_write_runner() -> AsyncIterator[WriteRunner | None]:
    """The Attio write step, or None when it is off or this instance is flagged as test."""
    settings = get_settings()
    mode = settings.interactions_attio_write_mode
    if mode is WriteMode.OFF:
        yield None
        return
    if attio_is_test():
        logger.error("interactions_attio_write_not_started: ATTIO_IS_TEST is set")
        yield None
        return
    sessionmaker = get_sessionmaker()
    internal = settings.internal_domains
    async with AsyncExitStack() as stack:
        service: AttioWriteService | None
        try:
            client = await stack.enter_async_context(get_attio_client())

            async def member_ids() -> Mapping[str, str]:
                members = await list_workspace_members(client)
                return {
                    team_member_of(m.email.strip().lower(), internal): m.member_id for m in members
                }

            service = AttioWriteService(
                SqlAlchemyTouchReader(sessionmaker, internal),
                SqlAlchemySentValues(sessionmaker),
                AttioRecordWriter(client, settings.interactions_attio_writes_per_second),
                SqlAlchemyScoreStore(sessionmaker),
                member_ids,
                AttioWriteConfig(
                    read_mailboxes=frozenset(
                        team_member_of(m, internal) for m in settings.mailboxes
                    ),
                    rules=settings.scoring_rules(),
                    max_records_per_round=settings.interactions_attio_max_records_per_round,
                    dry_run=mode is WriteMode.DRY_RUN,
                ),
                _utc_now,
            )
            logger.info("interactions_attio_write_enabled mode=%s", mode.value)
        except Exception:
            # The write step is optional; a failure here must never stop mail ingestion.
            logger.exception("interactions_attio_write_not_started: setup failed")
            service = None
        yield service


async def run_strength_calibration() -> CalibrationReport:
    """One read-only comparison of our labels with Attio's. Writes nothing anywhere."""
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    internal = settings.internal_domains
    config = CalibrationConfig(
        read_mailboxes=frozenset(team_member_of(m, internal) for m in settings.mailboxes),
        internal_domains=internal,
        rules=settings.scoring_rules(),
    )
    async with get_attio_client() as client:
        return await run_calibration(
            AttioStrengthSource(client, internal),
            SqlAlchemyTouchReader(sessionmaker, internal),
            SqlAlchemyRecordDirectory(sessionmaker),
            config,
            _utc_now(),
        )


async def run_attio_seed() -> tuple[SeedReport, ...]:
    """Record what Attio holds today. Reads Attio, writes only `attio_sent_values`."""
    async with get_attio_client() as client:
        return await AttioSeedService(
            AttioSeedSource(client), SqlAlchemySentValues(get_sessionmaker())
        ).run()
