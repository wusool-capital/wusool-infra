"""The peer dataset one benchmark score is computed against. Pure.

Built from the `benchmark_data` tables by `providers/benchmark_data`."""

from collections.abc import Mapping
from dataclasses import dataclass

from app.modules.lead_magnets.domain.benchmark.benchmark import Band, MetricSpec, Mode, PeerCut
from app.modules.lead_magnets.domain.benchmark.benchmark_dataset import (
    BANDS,
    SECTORS,
    SME_METRICS,
    STAGES,
    TECH_METRICS,
)


@dataclass(frozen=True)
class PeerDataset:
    bands: tuple[Band, ...]
    metrics: Mapping[Mode, Mapping[str, MetricSpec]]
    cuts: Mapping[Mode, Mapping[str, PeerCut]]


# The dataset as first loaded. Used only when the tables can't be read, so a score is always
# produced, as it was when the data lived in code.
BUILT_IN_PEER_DATASET = PeerDataset(
    bands=BANDS,
    metrics={"sme": SME_METRICS, "tech": TECH_METRICS},
    cuts={"sme": SECTORS, "tech": STAGES},
)
