"""A database error must not stop a benchmark from being scored."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.benchmark_data import BenchmarkDataset
from app.modules.benchmark_data.domain.dataset import Band, Metric, PeerCut
from app.modules.lead_magnets import bootstrap
from app.modules.lead_magnets.domain.benchmark.peer_dataset import BUILT_IN_PEER_DATASET

_AT = datetime(2026, 11, 15, tzinfo=UTC)
_STORED = BenchmarkDataset(
    updated_at=_AT,
    bands=(Band(uuid4(), "only", "Only", None, 0, 1, 1, "Ramzy", _AT),),
    metrics={
        "sme": {"gm": Metric(uuid4(), "gm", "Gross margin", "%", True, 100, None, "Ramzy", _AT)},
        "tech": {},
    },
    cuts={
        "sme": {
            "salon": PeerCut(
                uuid4(),
                "sme",
                "salon",
                "Salon",
                9,
                True,
                False,
                {"gm": (1, 2, 3, 4, 5)},
                "Ramzy",
                _AT,
            )
        },
        "tech": {},
    },
)


async def test_the_stored_dataset_is_used_when_it_can_be_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def load() -> BenchmarkDataset:
        return _STORED

    monkeypatch.setattr(bootstrap, "load_dataset", load)
    dataset = await bootstrap.load_peer_dataset()
    assert dataset is not BUILT_IN_PEER_DATASET
    assert dataset.cuts["sme"]["salon"].sample_size == 9


async def test_the_built_in_dataset_is_used_when_the_database_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def load() -> BenchmarkDataset:
        raise ConnectionError("database down")

    monkeypatch.setattr(bootstrap, "load_dataset", load)
    dataset = await bootstrap.load_peer_dataset()
    assert dataset is BUILT_IN_PEER_DATASET
    assert "benchmark_peer_dataset_fallback" in caplog.text


async def test_the_port_adapter_falls_back_too(monkeypatch: pytest.MonkeyPatch) -> None:
    async def load() -> BenchmarkDataset:
        raise ConnectionError("database down")

    monkeypatch.setattr(bootstrap, "load_dataset", load)
    assert await bootstrap._BenchmarkDataPeers().load() is BUILT_IN_PEER_DATASET
