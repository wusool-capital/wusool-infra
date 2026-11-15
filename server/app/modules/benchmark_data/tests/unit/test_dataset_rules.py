"""The rules an edit must pass, and the service that applies them, against an
in-memory repository."""

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from app.modules.benchmark_data.application.service import BenchmarkDataService
from app.modules.benchmark_data.domain.dataset import (
    Anchors,
    Band,
    BandEdit,
    BenchmarkDataset,
    InvalidEditError,
    Metric,
    Mode,
    PeerCut,
    PeerCutEdit,
    UnknownRecordError,
)


def _dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        version=1,
        updated_at=datetime(2026, 11, 15, tzinfo=UTC),
        bands=(
            Band("micro", "Under 1m", 1_000_000, -3, 0.8, 1.25),
            Band("small", "1m to 5m", 5_000_000, 0, 1.0, 1.0),
            Band("upper", "5m and above", None, 4, 1.4, 0.82),
        ),
        metrics={
            "sme": {
                "ebitda": Metric("ebitda", "Margin", "%", True, 60, None),
                "growth": Metric("growth", "Growth", "%", True, 40, None),
            },
            "tech": {"growth": Metric("growth", "Growth", "%", True, 100, True)},
        },
        cuts={
            "sme": {
                "salon": PeerCut(
                    "sme",
                    "salon",
                    "Salon",
                    48,
                    True,
                    False,
                    {"ebitda": (3, 8, 14, 21, 28), "dso": (0, 2, 5, 12, 25)},
                )
            },
            "tech": {},
        },
    )


class FakeRepository:
    def __init__(self) -> None:
        self.dataset = _dataset()
        self.saved: list[str] = []
        self.version_bumps = 0

    async def load(self) -> BenchmarkDataset:
        return self.dataset

    async def save_peer_cut(self, cut: PeerCut, *, edited_by: str) -> None:
        self.saved.append(f"cut:{cut.key}:{edited_by}")

    async def save_band(self, band: Band, *, edited_by: str) -> None:
        self.saved.append(f"band:{band.id}")

    async def save_weights(self, mode: Mode, weights: Mapping[str, int], *, edited_by: str) -> None:
        self.saved.append(f"weights:{mode}")

    async def bump_version(self, *, edited_by: str) -> int:
        self.version_bumps += 1
        return self.dataset.version + self.version_bumps


@pytest.fixture
def repo() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def service(repo: FakeRepository) -> BenchmarkDataService:
    return BenchmarkDataService(repo)


async def test_peer_cut_edit_changes_only_the_fields_sent(
    service: BenchmarkDataService, repo: FakeRepository
) -> None:
    anchors: Mapping[str, Anchors] = {"ebitda": (4, 9, 15, 22, 29)}
    cut = await service.edit_peer_cut(
        "sme", "salon", PeerCutEdit(sample_size=60, anchors=anchors), edited_by="Alice"
    )
    assert cut.sample_size == 60
    assert cut.anchors["ebitda"] == (4, 9, 15, 22, 29)
    assert cut.anchors["dso"] == (0, 2, 5, 12, 25)
    assert cut.multi_site is True
    assert repo.saved == ["cut:salon:Alice"]
    assert repo.version_bumps == 1


async def test_anchors_that_do_not_rise_are_refused(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="rise from p10 to p90"):
        await service.edit_peer_cut(
            "sme", "salon", PeerCutEdit(anchors={"ebitda": (9, 8, 14, 21, 28)}), edited_by="A"
        )


async def test_a_metric_the_mode_does_not_have_is_refused(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="not a metric"):
        await service.edit_peer_cut(
            "sme", "salon", PeerCutEdit(anchors={"fwdMult": (1, 2, 3, 4, 5)}), edited_by="A"
        )


async def test_an_unknown_peer_cut_is_refused(service: BenchmarkDataService) -> None:
    with pytest.raises(UnknownRecordError):
        await service.edit_peer_cut("sme", "nope", PeerCutEdit(sample_size=5), edited_by="A")


async def test_a_refused_edit_saves_nothing_and_keeps_the_version(
    service: BenchmarkDataService, repo: FakeRepository
) -> None:
    with pytest.raises(InvalidEditError):
        await service.edit_peer_cut("sme", "salon", PeerCutEdit(sample_size=-1), edited_by="A")
    assert repo.saved == []
    assert repo.version_bumps == 0


async def test_band_edit_saves_only_that_band(
    service: BenchmarkDataService, repo: FakeRepository
) -> None:
    bands = await service.edit_band("micro", BandEdit(max_usd=900_000), edited_by="A")
    assert bands[0].max_usd == 900_000
    assert repo.saved == ["band:micro"]


async def test_band_ceilings_must_keep_rising(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="must rise"):
        await service.edit_band("micro", BandEdit(max_usd=6_000_000), edited_by="A")


async def test_only_the_top_band_is_open_ended(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="Only the top band"):
        await service.edit_band("upper", BandEdit(max_usd=9_000_000), edited_by="A")


async def test_band_multipliers_must_be_positive(service: BenchmarkDataService) -> None:
    with pytest.raises(InvalidEditError, match="above zero"):
        await service.edit_band("small", BandEdit(rent_mult=0), edited_by="A")


async def test_an_unknown_band_is_refused(service: BenchmarkDataService) -> None:
    with pytest.raises(UnknownRecordError):
        await service.edit_band("huge", BandEdit(label="x"), edited_by="A")


async def test_weights_are_saved_when_they_total_100(
    service: BenchmarkDataService, repo: FakeRepository
) -> None:
    await service.set_weights("sme", {"ebitda": 70, "growth": 30}, edited_by="A")
    assert repo.saved == ["weights:sme"]
    assert repo.version_bumps == 1


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
        await service.set_weights("sme", weights, edited_by="A")
