"""The seam to the benchmark peer dataset. Implemented in `bootstrap.py` over
the `benchmark_data` module; faked in tests."""

from typing import Protocol

from app.modules.lead_magnets.domain.benchmark.peer_dataset import PeerDataset


class PeerDatasetPort(Protocol):
    async def load(self) -> PeerDataset: ...
