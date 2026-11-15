"""The built-in peer dataset as a port, for tests that score without a database."""

from app.modules.lead_magnets.domain.benchmark.peer_dataset import (
    BUILT_IN_PEER_DATASET,
    PeerDataset,
)

__all__ = ["BUILT_IN_PEER_DATASET", "BuiltInPeerDatasets"]


class BuiltInPeerDatasets:
    async def load(self) -> PeerDataset:
        return BUILT_IN_PEER_DATASET
