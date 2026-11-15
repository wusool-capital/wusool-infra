"""Storage for the benchmark dataset. Implementations never expose ORM types."""

from collections.abc import Mapping
from typing import Protocol

from app.modules.benchmark_data.domain.dataset import (
    Band,
    BenchmarkDataset,
    Editor,
    Metric,
    Mode,
    PeerCut,
)


class BenchmarkDataRepository(Protocol):
    async def load(self, *, for_update: bool = False) -> BenchmarkDataset:
        """With `for_update`, locks every row until the transaction ends, so two edits
        can't each merge onto the same snapshot and overwrite one another."""
        ...

    async def save_peer_cut(self, cut: PeerCut, *, editor: Editor) -> PeerCut:
        """Writes the cut and returns it as stored, with who changed it and when."""
        ...

    async def save_band(self, band: Band, *, editor: Editor) -> Band: ...

    async def save_weights(
        self, mode: Mode, weights: Mapping[str, int], *, editor: Editor
    ) -> Mapping[str, Metric]:
        """Updates the weights that differ and returns all of the mode's metrics."""
        ...
