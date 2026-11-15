"""The Postgres adapter against a real database, and the seed against the
dataset it was taken from."""

import pytest

from app.modules.benchmark_data.application.service import BenchmarkDataService
from app.modules.benchmark_data.domain.dataset import (
    BandEdit,
    InvalidEditError,
    PeerCutEdit,
)
from app.modules.benchmark_data.persistence.repository import PostgresBenchmarkDataRepository
from app.modules.lead_magnets.domain.benchmark import benchmark_dataset as source


@pytest.fixture
def service(db_session) -> BenchmarkDataService:
    return BenchmarkDataService(PostgresBenchmarkDataRepository(db_session))


async def test_the_seed_matches_benchmark_dataset_py(db_session) -> None:
    """Scores must not move when the tool starts reading the table."""
    dataset = await PostgresBenchmarkDataRepository(db_session).load()

    assert [
        (b.id, b.label, b.max_usd, b.ebitda_adj, b.rev_emp_mult, b.rent_mult) for b in dataset.bands
    ] == [
        (b.id, b.label, b.max_usd, b.ebitda_adj, b.rev_emp_mult, b.rent_mult) for b in source.BANDS
    ]
    for mode, specs, cuts in (
        ("sme", source.SME_METRICS, source.SECTORS),
        ("tech", source.TECH_METRICS, source.STAGES),
    ):
        assert list(dataset.metrics[mode]) == list(specs)
        for key, spec in specs.items():
            stored = dataset.metrics[mode][key]
            assert (stored.label, stored.unit, stored.higher_is_better, stored.weight) == (
                spec.label,
                spec.unit,
                spec.higher_is_better,
                spec.weight,
            )
        assert set(dataset.cuts[mode]) == set(cuts)
        for key, cut in cuts.items():
            stored_cut = dataset.cuts[mode][key]
            assert (stored_cut.label, stored_cut.sample_size) == (cut.label, cut.sample_size)
            assert (stored_cut.multi_site, stored_cut.b2b) == (cut.multi_site, cut.b2b)
            assert {m: tuple(a) for m, a in cut.anchors.items()} == dict(stored_cut.anchors)


async def test_an_edit_is_stored_attributed_and_bumps_the_version(
    service: BenchmarkDataService,
) -> None:
    before = await service.dataset()
    await service.edit_peer_cut(
        "sme",
        "salon",
        PeerCutEdit(sample_size=99, anchors={"gm": (60, 66, 72, 77, 82)}),
        edited_by="Alice",
    )
    after = await service.dataset()
    assert after.version == before.version + 1
    assert after.cuts["sme"]["salon"].sample_size == 99
    assert after.cuts["sme"]["salon"].anchors["gm"] == (60, 66, 72, 77, 82)
    assert (
        after.cuts["sme"]["salon"].anchors["ebitda"]
        == before.cuts["sme"]["salon"].anchors["ebitda"]
    )


async def test_a_band_edit_is_stored(service: BenchmarkDataService) -> None:
    await service.edit_band("micro", BandEdit(ebitda_adj=-2.5), edited_by="Alice")
    assert (await service.dataset()).bands[0].ebitda_adj == -2.5


async def test_weights_are_stored(service: BenchmarkDataService) -> None:
    await service.set_weights(
        "tech",
        {"growth": 30, "capEff": 20, "revScale": 15, "gm": 10, "recur": 15, "conc": 10},
        edited_by="Alice",
    )
    assert (await service.dataset()).metrics["tech"]["growth"].weight == 30


async def test_a_refused_edit_leaves_the_version_alone(service: BenchmarkDataService) -> None:
    before = await service.dataset()
    with pytest.raises(InvalidEditError):
        await service.set_weights("sme", {"ebitda": 1}, edited_by="Alice")
    assert (await service.dataset()).version == before.version
