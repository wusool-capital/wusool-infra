"""Storage for the benchmark dataset. Implementations never expose ORM types."""

from collections.abc import Mapping
from typing import Protocol

from app.modules.benchmark_data.domain.dataset import Band, BenchmarkDataset, Mode, PeerCut


class BenchmarkDataRepository(Protocol):
    async def load(self) -> BenchmarkDataset: ...

    async def save_peer_cut(self, cut: PeerCut, *, edited_by: str) -> None: ...

    async def save_band(self, band: Band, *, edited_by: str) -> None: ...

    async def save_weights(
        self, mode: Mode, weights: Mapping[str, int], *, edited_by: str
    ) -> None: ...

    async def bump_version(self, *, edited_by: str) -> int: ...
