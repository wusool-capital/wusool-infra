"""CSP and cache policy for the embeddable tool pages.

Uses a temporary directory rather than the real `static/`, which is empty
until the tool pages are imported — the headers are independent of the
content anyway.
"""

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from app.modules.lead_magnets.api.static import ToolStatic


@pytest.fixture
def client(tmp_path):
    (tmp_path / "img").mkdir()
    (tmp_path / "embed.js").write_text("// loader")
    (tmp_path / "img" / "abc12345.png").write_bytes(b"\x89PNG")
    (tmp_path / "valuation.html").write_text("<h1>valuation</h1>")

    app = Starlette()
    app.mount("/", ToolStatic(directory=tmp_path, html=True), name="tools")
    return TestClient(app)


def test_frame_ancestors_is_set_and_xfo_is_not(client) -> None:
    """`X-Frame-Options` has no working allow-list value, so setting it at
    all would block the Webflow embed outright."""
    response = client.get("/embed.js")
    assert response.status_code == 200
    assert "frame-ancestors" in response.headers["content-security-policy"]
    assert "wusoolcapital.com" in response.headers["content-security-policy"]
    assert "x-frame-options" not in response.headers


def test_embed_js_is_short_cached(client) -> None:
    """It is both the cutover switch and the rollback switch — a long TTL
    here is how a rollback takes an hour instead of a minute."""
    assert client.get("/embed.js").headers["cache-control"] == "public, max-age=60"


def test_content_addressed_images_are_immutable(client) -> None:
    response = client.get("/img/abc12345.png")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_tool_page_is_short_cached_and_nosniff(client) -> None:
    response = client.get("/valuation.html")
    assert response.headers["cache-control"] == "public, max-age=60"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_extensionless_paths_are_not_served(client) -> None:
    """Starlette's `html=True` serves `index.html` for a *directory*; it does
    not map `/valuation` to `valuation.html` the way nginx would. So
    `embed.js` must point the iframe at the full filename — asserted here so
    nobody rediscovers it against a 404 in production."""
    assert client.get("/valuation").status_code == 404
    assert client.get("/valuation.html").status_code == 200
