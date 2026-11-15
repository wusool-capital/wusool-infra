"""Reading and editing the benchmark dataset. Every edit is checked against the
dataset it lands in and bumps the dataset version."""

from collections.abc import Mapping

from app.modules.benchmark_data.application.ports.repository import BenchmarkDataRepository
from app.modules.benchmark_data.domain.dataset import (
    Band,
    BandEdit,
    BenchmarkDataset,
    Edited,
    Mode,
    PeerCut,
    PeerCutEdit,
    UnknownRecordError,
    apply_band_edit,
    apply_peer_cut_edit,
    check_weights,
)


class BenchmarkDataService:
    def __init__(self, repository: BenchmarkDataRepository) -> None:
        self._repository = repository

    async def dataset(self) -> BenchmarkDataset:
        return await self._repository.load()

    async def edit_peer_cut(
        self, mode: Mode, key: str, edit: PeerCutEdit, *, edited_by: str
    ) -> Edited[PeerCut]:
        dataset = await self._repository.load()
        cut = dataset.cuts[mode].get(key)
        if cut is None:
            raise UnknownRecordError(f"No {mode} peer cut '{key}'")
        updated = apply_peer_cut_edit(cut, edit, dataset.metrics[mode])
        await self._repository.save_peer_cut(updated, edited_by=edited_by)
        version = await self._repository.bump_version(edited_by=edited_by)
        return Edited(updated, version)

    async def edit_band(
        self, band_id: str, edit: BandEdit, *, edited_by: str
    ) -> Edited[tuple[Band, ...]]:
        dataset = await self._repository.load()
        bands = apply_band_edit(dataset.bands, band_id, edit)
        edited = next(b for b in bands if b.id == band_id)
        await self._repository.save_band(edited, edited_by=edited_by)
        version = await self._repository.bump_version(edited_by=edited_by)
        return Edited(bands, version)

    async def set_weights(
        self, mode: Mode, weights: Mapping[str, int], *, edited_by: str
    ) -> Edited[Mapping[str, int]]:
        dataset = await self._repository.load()
        check_weights(dataset.metrics[mode], weights)
        await self._repository.save_weights(mode, weights, edited_by=edited_by)
        version = await self._repository.bump_version(edited_by=edited_by)
        return Edited(weights, version)
