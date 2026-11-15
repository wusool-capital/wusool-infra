"""The page's `DATA` script: rendered from the tables, with the static file as
the fallback when they cannot be read."""

import json
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.benchmark_data import BenchmarkDataset
from app.modules.benchmark_data.domain.dataset import Band, Metric, PeerCut
from app.modules.lead_magnets.api.benchmark import dataset_script
from app.modules.lead_magnets.api.static import static_dir
from app.modules.lead_magnets.domain.benchmark.dataset_js import render_dataset_js


def _dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        version=7,
        updated_at=datetime(2026, 11, 15, tzinfo=UTC),
        bands=(
            Band("micro", "Under 1m", 1_000_000, -3, 0.8, 1.25),
            Band("top", "Top", None, 4, 1.4, 0.8),
        ),
        metrics={
            "sme": {"ebitda": Metric("ebitda", "Margin", "%", True, 100, None)},
            "tech": {"growth": Metric("growth", "Growth", "%", True, 100, True)},
        },
        cuts={
            "sme": {
                "salon": PeerCut(
                    "sme", "salon", "Salon", 48, True, False, {"ebitda": (3, 8, 14, 21, 28)}
                )
            },
            "tech": {
                "seed": PeerCut(
                    "tech", "seed", "Seed", 15, False, False, {"growth": (76, 117, 150, 267, 400)}
                )
            },
        },
    )


def _data(script: str) -> dict:
    assert script.startswith("const DATA = ") and script.endswith(";\n")
    return json.loads(script.removeprefix("const DATA = ").removesuffix(";\n"))


def test_the_script_has_the_shape_the_page_reads() -> None:
    data = _data(render_dataset_js(_dataset(), ["AI", "SaaS"]))
    assert data["version"] == 7
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
    assert _data(response.text)["version"] == 7


def test_the_route_falls_back_to_the_static_file_when_the_database_fails(
    client: TestClient, monkeypatch
) -> None:
    async def load() -> BenchmarkDataset:
        raise ConnectionError("database down")

    monkeypatch.setattr(dataset_script, "load_dataset", load)
    response = client.get("/benchmark/20-data.js")
    assert response.status_code == 200
    assert response.text == (static_dir() / "benchmark" / "20-data.js").read_text(encoding="utf-8")
