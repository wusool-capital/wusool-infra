"""The `benchmark_data` module as this module's `PeerDatasetPort`.

Reads only that module's public exports, so nothing in `domain/` depends on it: the mapping to
this module's own scoring types lives here.
"""

import logging

from app.modules.benchmark_data import BenchmarkDataset, load_dataset
from app.modules.lead_magnets.domain.benchmark.benchmark import Band, MetricSpec, PeerCut
from app.modules.lead_magnets.domain.benchmark.peer_dataset import (
    BUILT_IN_PEER_DATASET,
    PeerDataset,
)

logger = logging.getLogger(__name__)


def peer_dataset_from(dataset: BenchmarkDataset) -> PeerDataset:
    return PeerDataset(
        bands=tuple(
            Band(
                id=b.code,
                label=b.label,
                max_usd=b.max_usd,
                ebitda_adj=b.ebitda_adj,
                rev_emp_mult=b.rev_emp_mult,
                rent_mult=b.rent_mult,
            )
            for b in dataset.bands
        ),
        metrics={
            mode: {
                key: MetricSpec(
                    label=m.label,
                    unit=m.unit,
                    higher_is_better=m.higher_is_better,
                    weight=m.weight,
                )
                for key, m in metrics.items()
            }
            for mode, metrics in dataset.metrics.items()
        },
        cuts={
            mode: {
                key: PeerCut(
                    label=c.label,
                    sample_size=c.sample_size,
                    anchors=c.anchors,
                    multi_site=c.multi_site,
                    b2b=c.b2b,
                )
                for key, c in cuts.items()
            }
            for mode, cuts in dataset.cuts.items()
        },
    )


async def load_peer_dataset() -> PeerDataset:
    """The stored peer dataset, or the original one when the tables can't be read.

    Scoring used to be pure; a database blip must not turn a visitor's result into a 500, or a
    recorded lead into a run that never reaches Attio.
    """
    try:
        return peer_dataset_from(await load_dataset())
    except Exception:
        logger.exception("benchmark_peer_dataset_fallback")
        return BUILT_IN_PEER_DATASET


class BenchmarkDataPeerDatasets:
    async def load(self) -> PeerDataset:
        return await load_peer_dataset()
