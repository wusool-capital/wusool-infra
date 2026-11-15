"""The GCC SME Benchmark's peer dataset in Postgres: revenue bands, metric
weights, peer cuts and their percentile anchors, with the rules an edit must
pass. The benchmark tool reads it; advisors edit it through the MCP. Each edit
leaves an `activities` event naming the person.
"""

from app.modules.benchmark_data.bootstrap import (
    edit_band,
    edit_peer_cut,
    load_dataset,
    set_weights,
)
from app.modules.benchmark_data.domain.dataset import (
    ANCHOR_ONLY_KEYS,
    METRIC_KEYS,
    Anchors,
    Band,
    BandEdit,
    BenchmarkDataset,
    Editor,
    InvalidEditError,
    Metric,
    Mode,
    PeerCut,
    PeerCutEdit,
    PercentileEdit,
    UnknownRecordError,
)

__all__ = [
    "ANCHOR_ONLY_KEYS",
    "METRIC_KEYS",
    "Anchors",
    "Band",
    "BandEdit",
    "BenchmarkDataset",
    "Editor",
    "InvalidEditError",
    "Metric",
    "Mode",
    "PeerCut",
    "PeerCutEdit",
    "PercentileEdit",
    "UnknownRecordError",
    "edit_band",
    "edit_peer_cut",
    "load_dataset",
    "set_weights",
]
