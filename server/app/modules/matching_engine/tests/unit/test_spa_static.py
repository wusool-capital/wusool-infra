from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.matching_engine.api.http.spa import mount_web_app, web_app_dist


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "index-abc.js").write_text("console.log(1)")
    return tmp_path


@pytest.fixture
def client(dist: Path) -> TestClient:
    app = FastAPI()
    mount_web_app(app, dist)
    return TestClient(app)


def test_deep_link_falls_back_to_index(client: TestClient) -> None:
    response = client.get("/app/runs/123")

    assert response.status_code == 200
    assert "root" in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_hashed_asset_is_immutable(client: TestClient) -> None:
    response = client.get("/app/assets/index-abc.js")

    assert response.status_code == 200
    assert "immutable" in response.headers["cache-control"]


def test_missing_asset_stays_404(client: TestClient) -> None:
    assert client.get("/app/assets/index-old.js").status_code == 404


def test_web_app_dist_prefers_image_copy(tmp_path: Path) -> None:
    server = tmp_path / "server"
    (server / "client-dist").mkdir(parents=True)
    (server / "client-dist" / "index.html").write_text("x")

    assert web_app_dist(server) == server / "client-dist"


def test_web_app_dist_missing_build(tmp_path: Path) -> None:
    assert web_app_dist(tmp_path / "server") is None


def test_bare_app_path_redirects_to_the_app(client: TestClient) -> None:
    response = client.get("/app", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "/app/"


def test_redirect_keeps_the_query_string(client: TestClient) -> None:
    response = client.get("/app?next=runs", follow_redirects=False)

    assert response.headers["location"] == "/app/?next=runs"


def test_bare_app_path_lands_on_the_app(client: TestClient) -> None:
    response = client.get("/app")

    assert response.status_code == 200
    assert "root" in response.text
