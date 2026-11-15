"""The rules an edit must pass, and the service that applies them, against an
in-memory repository and activity recorder."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.activities import (
    ActivityEvent,
    ActivitySource,
    ActorType,
    BenchmarkEditPayload,
    EventType,
    SubjectType,
)
from app.modules.benchmark_data.application.service import BenchmarkDataService
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
    PercentileEdit,
    UnknownRecordError,
)

_THEN = datetime(2026, 11, 1, tzinfo=UTC)
_NOW = datetime(2026, 11, 15, tzinfo=UTC)
_ALICE = Editor(slack_user_id="U_ALICE", name="Alice Jones")


def _band(
    code: str, label: str, max_usd: float | None, adj: float, emp: float, rent: float
) -> Band:
    return Band(uuid4(), code, label, max_usd, adj, emp, rent, "seed", _THEN)


def _metric(key: str, weight: int, observed: bool | None = None) -> Metric:
    return Metric(uuid4(), key, key.title(), "%", True, weight, observed, "seed", _THEN)


def _dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        updated_at=_THEN,
        bands=(
            _band("micro", "Under 1m", 1_000_000, -3, 0.8, 1.25),
            _band("small", "1m to 5m", 5_000_000, 0, 1.0, 1.0),
            _band("upper", "5m and above", None, 4, 1.4, 0.82),
        ),
        metrics={
            "sme": {"ebitda": _metric("ebitda", 60), "growth": _metric("growth", 40)},
            "tech": {"growth": _metric("growth", 100, True)},
        },
        cuts={
            "sme": {
                "salon": PeerCut(
                    uuid4(),
                    "sme",
                    "salon",
                    "Salon",
                    48,
                    True,
                    False,
                    {"ebitda": (3, 8, 14, 21, 28), "dso": (0, 2, 5, 12, 25)},
                    "seed",
                    _THEN,
                )
            },
            "tech": {},
        },
    )


class FakeRepository:
    def __init__(self) -> None:
        self.dataset = _dataset()
        self.saved: list[str] = []

    async def load(self) -> BenchmarkDataset:
        return self.dataset

    async def save_peer_cut(self, cut: PeerCut, *, edited_by: str) -> PeerCut:
        self.saved.append(f"cut:{cut.key}:{edited_by}")
        return replace(cut, updated_by=edited_by, updated_at=_NOW)

    async def save_band(self, band: Band, *, edited_by: str) -> Band:
        self.saved.append(f"band:{band.code}:{edited_by}")
        return replace(band, updated_by=edited_by, updated_at=_NOW)

    async def save_weights(
        self, mode: Mode, weights: Mapping[str, int], *, edited_by: str
    ) -> Mapping[str, Metric]:
        self.saved.append(f"weights:{mode}:{edited_by}")
        return {
            key: replace(m, weight=weights[key], updated_by=edited_by, updated_at=_NOW)
            if m.weight != weights[key]
            else m
            for key, m in self.dataset.metrics[mode].items()
        }


class FakeActivities:
    def __init__(self) -> None:
        self.events: list[ActivityEvent] = []

    async def record(self, event: ActivityEvent) -> None:
        self.events.append(event)


@pytest.fixture
def repo() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def activities() -> FakeActivities:
    return FakeActivities()


@pytest.fixture
def service(repo: FakeRepository, activities: FakeActivities) -> BenchmarkDataService:
    return BenchmarkDataService(repo, activities)


async def test_peer_cut_edit_changes_only_the_fields_sent(
    service: BenchmarkDataService, repo: FakeRepository
) -> None:
    anchors: Mapping[str, Anchors] = {"ebitda": (4, 9, 15, 22, 29)}
    cut = await service.edit_peer_cut(
        "sme",
        "salon",
        PeerCutEdit(sample_size=60, anchors=anchors),
        editor=_ALICE,
        source=ActivitySource.MCP,
    )
    assert cut.sample_size == 60
    assert cut.anchors["ebitda"] == (4, 9, 15, 22, 29)
    assert cut.anchors["dso"] == (0, 2, 5, 12, 25)
    assert cut.multi_site is True
    assert (cut.updated_by, cut.updated_at) == ("Alice Jones", _NOW)
    assert repo.saved == ["cut:salon:Alice Jones"]


async def test_the_row_shows_the_persons_name_and_the_activity_their_slack_id(
    service: BenchmarkDataService, activities: FakeActivities
) -> None:
    cut = await service.edit_peer_cut(
        "sme", "salon", PeerCutEdit(sample_size=60), editor=_ALICE, source=ActivitySource.MCP
    )
    (event,) = activities.events
    assert cut.updated_by == "Alice Jones"
    assert event.actor.type is ActorType.SLACK_USER
    assert event.actor.ref == "U_ALICE"
    assert event.source is ActivitySource.MCP
    assert event.subject_type is SubjectType.BENCHMARK_PEER_CUT
    assert event.event_type is EventType.BENCHMARK_PEER_CUT_EDITED
    assert event.subject_uuid == cut.id
    assert event.payload == BenchmarkEditPayload(changed_fields=("sample_size",))


async def test_without_a_name_the_row_falls_back_to_the_slack_id(
    service: BenchmarkDataService,
) -> None:
    cut = await service.edit_peer_cut(
        "sme",
        "salon",
        PeerCutEdit(sample_size=60),
        editor=Editor(slack_user_id="U_BOB"),
        source=ActivitySource.MCP,
    )
    assert cut.updated_by == "U_BOB"


async def test_the_activity_names_each_changed_anchor_and_nothing_else(
    service: BenchmarkDataService, activities: FakeActivities
) -> None:
    await service.edit_peer_cut(
        "sme",
        "salon",
        PeerCutEdit(
            sample_size=48,
            anchors={"ebitda": (4, 9, 15, 22, 29), "dso": (0, 2, 5, 12, 25)},
        ),
        editor=_ALICE,
        source=ActivitySource.MCP,
    )
    (event,) = activities.events
    assert event.payload == BenchmarkEditPayload(changed_fields=("anchors.ebitda",))


async def test_an_edit_that_changes_nothing_saves_and_records_nothing(
    service: BenchmarkDataService, repo: FakeRepository, activities: FakeActivities
) -> None:
    cut = await service.edit_peer_cut(
        "sme", "salon", PeerCutEdit(sample_size=48), editor=_ALICE, source=ActivitySource.MCP
    )
    assert cut.updated_by == "seed"
    assert repo.saved == []
    assert activities.events == []


async def test_anchors_that_do_not_rise_are_refused(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="rise from p10 to p90"):
        await service.edit_peer_cut(
            "sme",
            "salon",
            PeerCutEdit(anchors={"ebitda": (9, 8, 14, 21, 28)}),
            editor=_ALICE,
            source=ActivitySource.MCP,
        )


async def test_a_metric_the_mode_does_not_have_is_refused(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="not a metric"):
        await service.edit_peer_cut(
            "sme",
            "salon",
            PeerCutEdit(anchors={"fwdMult": (1, 2, 3, 4, 5)}),
            editor=_ALICE,
            source=ActivitySource.MCP,
        )


async def test_an_unknown_peer_cut_is_refused(service: BenchmarkDataService) -> None:
    with pytest.raises(UnknownRecordError):
        await service.edit_peer_cut(
            "sme", "nope", PeerCutEdit(sample_size=5), editor=_ALICE, source=ActivitySource.MCP
        )


async def test_a_refused_edit_saves_and_records_nothing(
    service: BenchmarkDataService, repo: FakeRepository, activities: FakeActivities
) -> None:
    with pytest.raises(InvalidEditError):
        await service.edit_peer_cut(
            "sme", "salon", PeerCutEdit(sample_size=-1), editor=_ALICE, source=ActivitySource.MCP
        )
    assert repo.saved == []
    assert activities.events == []


async def test_band_edit_saves_only_that_band_and_records_it(
    service: BenchmarkDataService, repo: FakeRepository, activities: FakeActivities
) -> None:
    bands = await service.edit_band(
        "micro", BandEdit(max_usd=900_000), editor=_ALICE, source=ActivitySource.MCP
    )
    assert bands[0].max_usd == 900_000
    assert bands[0].updated_by == "Alice Jones"
    assert bands[1].updated_by == "seed"
    assert repo.saved == ["band:micro:Alice Jones"]
    (event,) = activities.events
    assert event.subject_type is SubjectType.BENCHMARK_RULE
    assert event.event_type is EventType.BENCHMARK_RULE_EDITED
    assert event.subject_uuid == bands[0].id
    assert event.payload == BenchmarkEditPayload(changed_fields=("max_usd",))


async def test_band_ceilings_must_keep_rising(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="must rise"):
        await service.edit_band(
            "micro", BandEdit(max_usd=6_000_000), editor=_ALICE, source=ActivitySource.MCP
        )


async def test_only_the_top_band_is_open_ended(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="Only the top band"):
        await service.edit_band(
            "upper", BandEdit(max_usd=9_000_000), editor=_ALICE, source=ActivitySource.MCP
        )


async def test_band_multipliers_must_be_positive(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="above zero"):
        await service.edit_band(
            "small", BandEdit(rent_mult=0), editor=_ALICE, source=ActivitySource.MCP
        )


async def test_an_unknown_band_is_refused(service: BenchmarkDataService) -> None:
    with pytest.raises(UnknownRecordError):
        await service.edit_band(
            "huge", BandEdit(label="x"), editor=_ALICE, source=ActivitySource.MCP
        )


async def test_weights_record_one_event_per_changed_weight(
    service: BenchmarkDataService, repo: FakeRepository, activities: FakeActivities
) -> None:
    metrics = await service.set_weights(
        "sme", {"ebitda": 70, "growth": 30}, editor=_ALICE, source=ActivitySource.MCP
    )
    assert metrics["ebitda"].updated_by == "Alice Jones"
    assert repo.saved == ["weights:sme:Alice Jones"]
    assert {e.subject_uuid for e in activities.events} == {
        metrics["ebitda"].id,
        metrics["growth"].id,
    }
    assert all(
        e.payload == BenchmarkEditPayload(changed_fields=("weight",)) for e in activities.events
    )


async def test_unchanged_weights_save_and_record_nothing(
    service: BenchmarkDataService, repo: FakeRepository, activities: FakeActivities
) -> None:
    await service.set_weights(
        "sme", {"ebitda": 60, "growth": 40}, editor=_ALICE, source=ActivitySource.MCP
    )
    assert repo.saved == []
    assert activities.events == []


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ({"ebitda": 60, "growth": 30}, "add up to 100"),
        ({"ebitda": 100}, "every metric"),
        ({"ebitda": 60, "growth": 40, "gm": 0}, "every metric"),
        ({"ebitda": 110, "growth": -10}, "negative"),
    ],
)
async def test_bad_weights_are_refused(
    service: BenchmarkDataService, weights: dict[str, int], message: str
) -> None:
    with pytest.raises(InvalidEditError, match=message):
        await service.set_weights("sme", weights, editor=_ALICE, source=ActivitySource.MCP)


async def test_one_percentile_changes_alone_and_the_rest_keep_their_value(
    service: BenchmarkDataService, activities: FakeActivities
) -> None:
    cut = await service.edit_peer_cut(
        "sme",
        "salon",
        PeerCutEdit(anchors={"ebitda": PercentileEdit(p50=15)}),
        editor=_ALICE,
        source=ActivitySource.MCP,
    )
    assert cut.anchors["ebitda"] == (3, 8, 15, 21, 28)
    assert cut.anchors["dso"] == (0, 2, 5, 12, 25)
    (event,) = activities.events
    assert event.payload == BenchmarkEditPayload(changed_fields=("anchors.ebitda",))


async def test_a_partial_edit_can_mix_with_a_full_list_for_another_metric(
    service: BenchmarkDataService,
) -> None:
    cut = await service.edit_peer_cut(
        "sme",
        "salon",
        PeerCutEdit(
            anchors={"ebitda": PercentileEdit(p10=2, p90=30), "dso": (1, 2, 5, 12, 25)},
        ),
        editor=_ALICE,
        source=ActivitySource.MCP,
    )
    assert cut.anchors["ebitda"] == (2, 8, 14, 21, 30)
    assert cut.anchors["dso"] == (1, 2, 5, 12, 25)


async def test_a_partial_edit_that_breaks_the_order_is_refused(
    service: BenchmarkDataService, repo: FakeRepository
) -> None:
    with pytest.raises(InvalidEditError, match="rise from p10 to p90"):
        await service.edit_peer_cut(
            "sme",
            "salon",
            PeerCutEdit(anchors={"ebitda": PercentileEdit(p50=25)}),
            editor=_ALICE,
            source=ActivitySource.MCP,
        )
    assert repo.saved == []


async def test_a_partial_edit_needs_the_metric_to_have_anchors_already(
    service: BenchmarkDataService,
) -> None:
    with pytest.raises(InvalidEditError, match="no anchors yet"):
        await service.edit_peer_cut(
            "sme",
            "salon",
            PeerCutEdit(anchors={"growth": PercentileEdit(p50=9)}),
            editor=_ALICE,
            source=ActivitySource.MCP,
        )


async def test_a_partial_edit_naming_no_percentile_is_refused(
    service: BenchmarkDataService,
) -> None:
    with pytest.raises(InvalidEditError, match="at least one percentile"):
        await service.edit_peer_cut(
            "sme",
            "salon",
            PeerCutEdit(anchors={"ebitda": PercentileEdit()}),
            editor=_ALICE,
            source=ActivitySource.MCP,
        )
