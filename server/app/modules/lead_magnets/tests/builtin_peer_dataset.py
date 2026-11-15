"""The peer dataset as it stands in `benchmark_dataset.py`, as a `PeerDataset`.

Tests score against this so they pin the scoring algorithm; the Postgres seed
is checked against the same constants in `benchmark_data`'s own tests.
"""

from app.modules.lead_magnets.domain.benchmark.benchmark_dataset import (
    BANDS,
    SECTORS,
    SME_METRICS,
    STAGES,
    TECH_METRICS,
)
from app.modules.lead_magnets.domain.benchmark.peer_dataset import PeerDataset

BUILT_IN_PEER_DATASET = PeerDataset(
    bands=BANDS,
    metrics={"sme": SME_METRICS, "tech": TECH_METRICS},
    cuts={"sme": SECTORS, "tech": STAGES},
)


class BuiltInPeerDatasets:
    async def load(self) -> PeerDataset:
        return BUILT_IN_PEER_DATASET
