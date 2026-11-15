"""Storage for the benchmark dataset. Implementations never expose ORM types."""

from collections.abc import Mapping
from typing import Protocol

from app.modules.benchmark_data.domain.dataset import Band, BenchmarkDataset, Metric, Mode, PeerCut


class BenchmarkDataRepository(Protocol):
    async def load(self, *, for_update: bool = False) -> BenchmarkDataset:
        """With `for_update`, locks every row until the transaction ends, so two edits
        can't each merge onto the same snapshot and overwrite one another."""
        ...

    async def save_peer_cut(self, cut: PeerCut, *, edited_by: str) -> PeerCut:
        """Writes the cut and returns it as stored, with the new `updated_by`/`updated_at`."""
        ...

    async def save_band(self, band: Band, *, edited_by: str) -> Band: ...

    async def save_weights(
        self, mode: Mode, weights: Mapping[str, int], *, edited_by: str
    ) -> Mapping[str, Metric]:
        """Updates the weights that differ and returns all of the mode's metrics."""
        ...
