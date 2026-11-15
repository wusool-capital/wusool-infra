"""The page's `DATA` script: rendered from the tables, with the static file as
the fallback when they cannot be read."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.benchmark_data import BenchmarkDataset
from app.modules.benchmark_data.domain.dataset import Band, Metric, PeerCut
from app.modules.lead_magnets.api.benchmark import dataset_script
from app.modules.lead_magnets.api.benchmark.dataset_js import render_dataset_js
from app.modules.lead_magnets.api.static import static_dir

_AT = datetime(2026, 11, 15, tzinfo=UTC)


def _dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        updated_at=_AT,
        bands=(
            Band(uuid4(), "micro", "Under 1m", 1_000_000, -3, 0.8, 1.25, "seed", _AT),
            Band(uuid4(), "top", "Top", None, 4, 1.4, 0.8, "seed", _AT),
        ),
        metrics={
            "sme": {
                "ebitda": Metric(uuid4(), "ebitda", "Margin", "%", True, 100, None, "seed", _AT)
            },
            "tech": {
                "growth": Metric(uuid4(), "growth", "Growth", "%", True, 100, True, "seed", _AT)
            },
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
                    {"ebitda": (3, 8, 14, 21, 28)},
                    "seed",
                    _AT,
                )
            },
            "tech": {
                "seed": PeerCut(
                    uuid4(),
                    "tech",
                    "seed",
                    "Seed",
                    15,
                    False,
                    False,
                    {"growth": (76, 117, 150, 267, 400)},
                    "seed",
                    _AT,
                )
            },
        },
    )


def _data(script: str) -> dict:
    assert script.startswith("const DATA = ") and script.endswith(";\n")
    return json.loads(script.removeprefix("const DATA = ").removesuffix(";\n"))


def test_the_script_has_the_shape_the_page_reads() -> None:
    data = _data(render_dataset_js(_dataset(), ["AI", "SaaS"]))
    assert data["version"] == "2026-11-15T00:00:00+00:00"
    assert data["updated"] == "2026-11-15"
    assert data["bands"][0] == {
        "id": "micro",
        "label": "Under 1m",
        "max": 1_000_000,
        "ebitdaAdj": -3,
        "revEmpMult": 0.8,
        "rentMult": 1.25,
    }
    assert data["bands"][1]["max"] is None
    assert data["metrics"]["ebitda"] == {"label": "Margin", "unit": "%", "hi": True, "w": 100}
    assert data["techMetrics"]["growth"]["obs"] is True
    assert data["sectors"]["salon"] == {
        "label": "Salon",
        "multiSite": True,
        "b2b": False,
        "n": 48,
        "m": {"ebitda": [3, 8, 14, 21, 28]},
    }
    assert data["stages"]["seed"] == {
        "label": "Seed",
        "n": 15,
        "m": {"growth": [76, 117, 150, 267, 400]},
    }
    assert data["techSectorList"] == ["AI", "SaaS"]
    assert data["techCurrency"] == "USD"


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dataset_script, "_cached", None)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(dataset_script.router)
    return TestClient(app)


def test_the_route_serves_the_tables_as_javascript(client: TestClient, monkeypatch) -> None:
    async def load() -> BenchmarkDataset:
        return _dataset()

    monkeypatch.setattr(dataset_script, "load_dataset", load)
    response = client.get("/benchmark/20-data.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["cache-control"] == "public, max-age=60"
    assert _data(response.text)["version"].startswith("2026-11-15")


def test_the_route_falls_back_to_the_static_file_when_the_database_fails(
    client: TestClient, monkeypatch
) -> None:
    async def load() -> BenchmarkDataset:
        raise ConnectionError("database down")

    monkeypatch.setattr(dataset_script, "load_dataset", load)
    response = client.get("/benchmark/20-data.js")
    assert response.status_code == 200
    assert response.text == (static_dir() / "benchmark" / "20-data.js").read_text(encoding="utf-8")
    assert response.headers["cache-control"] == "no-store"


def test_a_burst_of_requests_reads_the_database_once(client: TestClient, monkeypatch) -> None:
    load = AsyncMock(return_value=_dataset())
    monkeypatch.setattr(dataset_script, "load_dataset", load)
    monkeypatch.setattr(dataset_script, "_clock", lambda: 100.0)
    for _ in range(5):
        assert client.get("/benchmark/20-data.js").status_code == 200
    assert load.await_count == 1


def test_the_script_is_rendered_again_once_the_cache_expires(
    client: TestClient, monkeypatch
) -> None:
    load = AsyncMock(return_value=_dataset())
    monkeypatch.setattr(dataset_script, "load_dataset", load)
    now = [100.0]
    monkeypatch.setattr(dataset_script, "_clock", lambda: now[0])
    client.get("/benchmark/20-data.js")
    now[0] += dataset_script._CACHE_SECONDS + 1
    client.get("/benchmark/20-data.js")
    assert load.await_count == 2


def test_a_failed_render_is_not_cached(client: TestClient, monkeypatch) -> None:
    load = AsyncMock(side_effect=[ConnectionError("down"), _dataset()])
    monkeypatch.setattr(dataset_script, "load_dataset", load)
    monkeypatch.setattr(dataset_script, "_clock", lambda: 100.0)
    first = client.get("/benchmark/20-data.js")
    second = client.get("/benchmark/20-data.js")
    assert first.headers["cache-control"] == "no-store"
    assert second.headers["cache-control"] == "public, max-age=60"
    assert load.await_count == 2
