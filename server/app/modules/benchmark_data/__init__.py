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
    UnknownRecordError,
)

__all__ = [
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
    "UnknownRecordError",
    "edit_band",
    "edit_peer_cut",
    "load_dataset",
    "set_weights",
]
