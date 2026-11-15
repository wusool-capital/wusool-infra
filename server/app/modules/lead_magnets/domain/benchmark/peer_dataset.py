"""The peer dataset one benchmark score is computed against, built from the
`benchmark_data` module's tables. Pure."""

from collections.abc import Mapping
from dataclasses import dataclass

from app.modules.benchmark_data.domain.dataset import BenchmarkDataset
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


# The dataset as first loaded. Used only when the tables can't be read, so a score is always
# produced, as it was when the data lived in code.
BUILT_IN_PEER_DATASET = PeerDataset(
    bands=BANDS,
    metrics={"sme": SME_METRICS, "tech": TECH_METRICS},
    cuts={"sme": SECTORS, "tech": STAGES},
)
