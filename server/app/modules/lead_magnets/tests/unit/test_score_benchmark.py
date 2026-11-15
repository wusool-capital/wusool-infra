"""One scoring serves the visitor, the stored run and the CRM write."""

from app.modules.lead_magnets.application.shared.pipelines import Pipelines, score_benchmark
from app.modules.lead_magnets.tests.builtin_peer_dataset import (
    BUILT_IN_PEER_DATASET,
    BuiltInPeerDatasets,
)

_PAYLOAD = {
    "mode": "sme",
    "peer_key": "restaurant",
    "revenue": 3_000_000,
    "prev_revenue": 2_700_000,
    "headcount": 40,
    "ebitda_reported": 400_000,
    "gross_margin_pct": 60,
    "email": "dana@acmegroup.ae",
    "consent": True,
}


def test_the_stored_output_is_the_result_the_visitor_sees() -> None:
    scored = score_benchmark(_PAYLOAD, BUILT_IN_PEER_DATASET)
    assert scored.output["score"] == scored.result.score
    assert scored.output["band"] == scored.result.band
    assert "entry_values" in scored.output


async def test_the_pipeline_produces_the_same_output() -> None:
    pipelines = Pipelines(llm=None, peer_datasets=BuiltInPeerDatasets())  # type: ignore[arg-type]
    assert await pipelines.run("benchmark", _PAYLOAD) == (
        score_benchmark(_PAYLOAD, BUILT_IN_PEER_DATASET).output
    )
