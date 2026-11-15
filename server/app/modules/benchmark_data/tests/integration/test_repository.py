"""The Postgres adapter against a real database, the activities an edit leaves,
and the seed against the dataset it was taken from."""

import pytest
from sqlalchemy import select

from app.models.activity import Activity
from app.modules.activities import ActivitySource, SqlAlchemyActivityRecorder
from app.modules.benchmark_data.application.service import BenchmarkDataService
from app.modules.benchmark_data.domain.dataset import (
    ANCHOR_ONLY_KEYS,
    METRIC_KEYS,
    BandEdit,
    Editor,
    InvalidEditError,
    PeerCutEdit,
    PercentileEdit,
)
from app.modules.benchmark_data.persistence.repository import PostgresBenchmarkDataRepository
from app.modules.lead_magnets.domain.benchmark import benchmark_dataset as source

_ALICE = Editor(slack_user_id="U_ALICE", name="Alice Jones")


@pytest.fixture
def service(db_session) -> BenchmarkDataService:
    return BenchmarkDataService(
        PostgresBenchmarkDataRepository(db_session), SqlAlchemyActivityRecorder(db_session)
    )


async def _activities(db_session, subject_uuid) -> list[Activity]:
    rows = await db_session.scalars(select(Activity).where(Activity.subject_uuid == subject_uuid))
    return list(rows)


async def test_the_seed_matches_benchmark_dataset_py(db_session) -> None:
    """Scores must not move when the tool starts reading the tables."""
    dataset = await PostgresBenchmarkDataRepository(db_session).load()

    assert [
        (b.code, b.label, b.max_usd, b.ebitda_adj, b.rev_emp_mult, b.rent_mult)
        for b in dataset.bands
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


async def test_every_seeded_row_says_it_came_from_the_seed(db_session) -> None:
    dataset = await PostgresBenchmarkDataRepository(db_session).load()
    rows = [*dataset.bands]
    rows += [m for mode in dataset.metrics.values() for m in mode.values()]
    rows += [c for mode in dataset.cuts.values() for c in mode.values()]
    assert {r.updated_by for r in rows} == {"seed"}
    assert {r.updated_by_name for r in rows} == {None}


async def test_an_edit_is_stored_with_the_slack_id_and_name_and_leaves_an_activity(
    service: BenchmarkDataService, db_session
) -> None:
    before = await service.dataset()
    cut = await service.edit_peer_cut(
        "sme",
        "salon",
        PeerCutEdit(sample_size=99, anchors={"gm": (60, 66, 72, 77, 82)}),
        editor=_ALICE,
        source=ActivitySource.MCP,
    )

    after = (await service.dataset()).cuts["sme"]["salon"]
    assert after.sample_size == 99
    assert after.anchors["gm"] == (60, 66, 72, 77, 82)
    assert after.anchors["ebitda"] == before.cuts["sme"]["salon"].anchors["ebitda"]
    assert (after.updated_by, after.updated_by_name) == ("U_ALICE", "Alice Jones")
    assert after.updated_at == cut.updated_at
    assert cut.updated_at > before.cuts["sme"]["salon"].updated_at

    (activity,) = await _activities(db_session, cut.id)
    assert activity.event_type == "benchmark.peer_cut_edited"
    assert activity.subject_type == "BenchmarkPeerCut"
    assert (activity.source, activity.actor_type, activity.actor_ref) == (
        "mcp",
        "slack_user",
        "U_ALICE",
    )
    assert activity.payload == {
        "kind": "benchmark_edit",
        "changed_fields": ["sample_size", "anchors.gm"],
    }


async def test_a_band_edit_is_stored_and_recorded(
    service: BenchmarkDataService, db_session
) -> None:
    bands = await service.edit_band(
        "micro", BandEdit(ebitda_adj=-2.5), editor=_ALICE, source=ActivitySource.MCP
    )
    stored = (await service.dataset()).bands[0]
    assert (stored.ebitda_adj, stored.updated_by, stored.updated_by_name) == (
        -2.5,
        "U_ALICE",
        "Alice Jones",
    )
    (activity,) = await _activities(db_session, bands[0].id)
    assert activity.event_type == "benchmark.rule_edited"
    assert activity.subject_type == "BenchmarkRule"


async def test_only_changed_weights_get_a_new_editor_and_an_activity(
    service: BenchmarkDataService, db_session
) -> None:
    metrics = await service.set_weights(
        "tech",
        {"growth": 30, "capEff": 20, "revScale": 15, "gm": 10, "recur": 15, "conc": 10},
        editor=_ALICE,
        source=ActivitySource.MCP,
    )
    assert (metrics["growth"].weight, metrics["growth"].updated_by) == (30, "U_ALICE")
    assert (metrics["gm"].weight, metrics["gm"].updated_by) == (10, "U_ALICE")
    assert metrics["capEff"].updated_by == "seed"
    assert len(await _activities(db_session, metrics["growth"].id)) == 1
    assert await _activities(db_session, metrics["capEff"].id) == []


async def test_a_refused_edit_changes_and_records_nothing(
    service: BenchmarkDataService, db_session
) -> None:
    before = await service.dataset()
    with pytest.raises(InvalidEditError):
        await service.set_weights("sme", {"ebitda": 1}, editor=_ALICE, source=ActivitySource.MCP)
    assert (await service.dataset()) == before


async def test_the_metric_keys_in_code_match_the_stored_rules_and_anchors(db_session) -> None:
    """The MCP tells callers these keys, so they must be what the tables hold."""
    dataset = await PostgresBenchmarkDataRepository(db_session).load()
    for mode in ("sme", "tech"):
        assert tuple(dataset.metrics[mode]) == METRIC_KEYS[mode]
        allowed = {*METRIC_KEYS[mode], *ANCHOR_ONLY_KEYS[mode]}
        for cut in dataset.cuts[mode].values():
            assert set(cut.anchors) == allowed, cut.key


async def test_one_percentile_is_stored_and_the_other_four_are_untouched(
    service: BenchmarkDataService, db_session
) -> None:
    before = (await service.dataset()).cuts["sme"]["restaurant"].anchors["gm"]
    cut = await service.edit_peer_cut(
        "sme",
        "restaurant",
        PeerCutEdit(anchors={"gm": PercentileEdit(p50=66)}),
        editor=_ALICE,
        source=ActivitySource.MCP,
    )
    stored = (await service.dataset()).cuts["sme"]["restaurant"].anchors["gm"]
    assert stored == (before[0], before[1], 66, before[3], before[4])
    assert cut.anchors["gm"] == stored
    (activity,) = await _activities(db_session, cut.id)
    assert activity.payload["changed_fields"] == ["anchors.gm"]
