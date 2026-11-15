"""Composition root. The module's public functions open a session, run one
service call in a transaction and commit, so callers never touch a session."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from app.modules.activities import ActivitySource, SqlAlchemyActivityRecorder
from app.modules.benchmark_data.application.service import BenchmarkDataService
from app.modules.benchmark_data.domain.dataset import (
    Band,
    BandEdit,
    BenchmarkDataset,
    Editor,
    Metric,
    Mode,
    PeerCut,
    PeerCutEdit,
)
from app.modules.benchmark_data.persistence.database import get_sessionmaker
from app.modules.benchmark_data.persistence.repository import PostgresBenchmarkDataRepository


@asynccontextmanager
async def _service() -> AsyncIterator[BenchmarkDataService]:
    async with get_sessionmaker()() as session, session.begin():
        yield BenchmarkDataService(
            PostgresBenchmarkDataRepository(session), SqlAlchemyActivityRecorder(session)
        )


async def load_dataset() -> BenchmarkDataset:
    async with _service() as service:
        return await service.dataset()


async def edit_peer_cut(
    mode: Mode, key: str, edit: PeerCutEdit, *, editor: Editor, source: ActivitySource
) -> PeerCut:
    async with _service() as service:
        return await service.edit_peer_cut(mode, key, edit, editor=editor, source=source)


async def edit_band(
    code: str, edit: BandEdit, *, editor: Editor, source: ActivitySource
) -> tuple[Band, ...]:
    async with _service() as service:
        return await service.edit_band(code, edit, editor=editor, source=source)


async def set_weights(
    mode: Mode, weights: Mapping[str, int], *, editor: Editor, source: ActivitySource
) -> Mapping[str, Metric]:
    async with _service() as service:
        return await service.set_weights(mode, weights, editor=editor, source=source)
