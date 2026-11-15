"""Composition root. The module's public functions open a session, run one
service call in a transaction and commit, so callers never touch a session."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from app.modules.benchmark_data.application.service import BenchmarkDataService
from app.modules.benchmark_data.domain.dataset import (
    Band,
    BandEdit,
    BenchmarkDataset,
    Edited,
    Mode,
    PeerCut,
    PeerCutEdit,
)
from app.modules.benchmark_data.persistence.database import get_sessionmaker
from app.modules.benchmark_data.persistence.repository import PostgresBenchmarkDataRepository


@asynccontextmanager
async def _service() -> AsyncIterator[BenchmarkDataService]:
    async with get_sessionmaker()() as session, session.begin():
        yield BenchmarkDataService(PostgresBenchmarkDataRepository(session))


async def load_dataset() -> BenchmarkDataset:
    async with _service() as service:
        return await service.dataset()


async def edit_peer_cut(
    mode: Mode, key: str, edit: PeerCutEdit, *, edited_by: str
) -> Edited[PeerCut]:
    async with _service() as service:
        return await service.edit_peer_cut(mode, key, edit, edited_by=edited_by)


async def edit_band(band_id: str, edit: BandEdit, *, edited_by: str) -> Edited[tuple[Band, ...]]:
    async with _service() as service:
        return await service.edit_band(band_id, edit, edited_by=edited_by)


async def set_weights(
    mode: Mode, weights: Mapping[str, int], *, edited_by: str
) -> Edited[Mapping[str, int]]:
    async with _service() as service:
        return await service.set_weights(mode, weights, edited_by=edited_by)
