"""The `DATA` script the benchmark page scores against in the browser, rendered
from the same tables the server scores against. Pure."""

import json
from collections.abc import Sequence

from app.modules.benchmark_data.domain.dataset import BenchmarkDataset, Metric, PeerCut

TECH_CURRENCY = "USD"


def _metric(metric: Metric) -> dict[str, str | bool | int | None]:
    shape: dict[str, str | bool | int | None] = {
        "label": metric.label,
        "unit": metric.unit,
        "hi": metric.higher_is_better,
        "w": metric.weight,
    }
    if metric.observed is not None:
        shape["obs"] = metric.observed
    return shape


def _cut(cut: PeerCut, *, sector: bool) -> dict[str, object]:
    shape: dict[str, object] = {"label": cut.label}
    if sector:
        shape |= {"multiSite": cut.multi_site, "b2b": cut.b2b}
    shape["n"] = cut.sample_size
    shape["m"] = {metric: list(values) for metric, values in cut.anchors.items()}
    return shape


def render_dataset_js(dataset: BenchmarkDataset, tech_sector_list: Sequence[str]) -> str:
    data = {
        "version": dataset.updated_at.isoformat(),
        "updated": dataset.updated_at.date().isoformat(),
        "bands": [
            {
                "id": b.code,
                "label": b.label,
                "max": b.max_usd,
                "ebitdaAdj": b.ebitda_adj,
                "revEmpMult": b.rev_emp_mult,
                "rentMult": b.rent_mult,
            }
            for b in dataset.bands
        ],
        "metrics": {k: _metric(m) for k, m in dataset.metrics["sme"].items()},
        "techCurrency": TECH_CURRENCY,
        "techMetrics": {k: _metric(m) for k, m in dataset.metrics["tech"].items()},
        "stages": {k: _cut(c, sector=False) for k, c in dataset.cuts["tech"].items()},
        "techSectorList": list(tech_sector_list),
        "sectors": {k: _cut(c, sector=True) for k, c in dataset.cuts["sme"].items()},
    }
    return f"const DATA = {json.dumps(data, separators=(',', ':'))};\n"
